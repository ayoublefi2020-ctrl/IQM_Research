"""Compare decoders on identical shots; choose on selection data and evaluate on fresh data."""
import argparse
import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from surface_code import make_stim_circuit
from qec_analysis import PROFILES, noise_model, matcher, failures, fit_rate, plot_curves


def sweep(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    configs = list(itertools.product(args.distances, args.bases, args.profiles, args.p, args.rounds))
    trials = np.random.SeedSequence(args.seed).spawn(2*len(configs)*args.repeats)
    decoders = ("plain", "correlated")
    report = {"settings": vars(args), "noise_multipliers": PROFILES, "phases": {}}
    for phase_i, phase in enumerate(("selection", "validation")):
        total = dict.fromkeys(decoders, 0)
        shots_total = plain_only = corr_only = 0
        curves = defaultdict(list)
        with (out / (phase+".csv")).open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow("distance basis profile p rounds repeat seed shots plain_errors correlated_errors plain_only correlated_only".split())
            for i,(d,b,profile,p,r) in enumerate(configs):
                c = make_stim_circuit(d,r,b,noise=noise_model(p,profile))
                models = [matcher(c,name) for name in decoders]
                counts = dict.fromkeys(decoders, 0)
                for rep in range(args.repeats):
                    idx = (phase_i*len(configs)+i)*args.repeats+rep
                    seed = int(trials[idx].generate_state(1,dtype=np.uint64)[0])
                    det, obs = c.compile_detector_sampler(seed=seed).sample(args.shots,separate_observables=True)
                    a,z = [failures(m,name,det,obs) for m,name in zip(models,decoders)]
                    ka,kz,az,za = map(int,(a.sum(),z.sum(),(a & ~z).sum(),(z & ~a).sum()))
                    writer.writerow((d,b,profile,p,r,rep,seed,args.shots,ka,kz,az,za))
                    counts["plain"] += ka
                    counts["correlated"] += kz
                    plain_only += az
                    corr_only += za
                    shots_total += args.shots
                for name in decoders:
                    total[name] += counts[name]
                    curves[d,b,profile,p,name].append((r,counts[name],args.shots*args.repeats))
        if phase == "selection":
            report["selected_decoder"] = min(total,key=total.get)
        report["phases"][phase] = dict(shots=shots_total,failures=total,plain_only=plain_only,
                                        correlated_only=corr_only, paired_p=binomtest(
                                        plain_only,plain_only+corr_only).pvalue if plain_only+corr_only else 1.)
        print(phase, report["phases"][phase], flush=True)
    selected = report["selected_decoder"]
    with (out/"validation_fits.csv").open("w",newline="") as f:
        writer = csv.writer(f)
        writer.writerow("distance basis profile p decoder rate low95 high95".split())
        for key, points in curves.items():
            fit = fit_rate(*zip(*points))
            writer.writerow((*key,fit["rate"],fit["low"],fit["high"]))
    d,b,profile,p = args.distances[0],args.bases[0],args.profiles[0],args.p[len(args.p)//2]
    plot_curves({name:list(zip(*curves[d,b,profile,p,name])) for name in decoders},
                out/"validation.png", f"Simulation: distance {d}, {b} memory, {profile}, p={p}")
    (out/"selection.json").write_text(json.dumps(report,indent=2))
    print("Selected:",selected,"; saved results in",out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--distances",nargs="+",type=int,default=[3,5])
    ap.add_argument("--bases",nargs="+",choices=["Z","X"],default=["Z","X"])
    ap.add_argument("--rounds",nargs="+",type=int,default=[2,3,5,8])
    ap.add_argument("--profiles",nargs="+",choices=PROFILES,default=list(PROFILES))
    ap.add_argument("--p",nargs="+",type=float,default=[.001,.003,.005,.01])
    ap.add_argument("--shots",type=int,default=4000)
    ap.add_argument("--repeats",type=int,default=2)
    ap.add_argument("--seed",type=int,default=20261121)
    ap.add_argument("--output",default="results/sweep")
    args=ap.parse_args()
    if args.shots<1 or args.repeats<1 or len(set(args.rounds))<2:
        ap.error("Use positive shots/repeats and two or more distinct round counts.")
    sweep(args)
