"""Use an independent pilot to select among four decoders, then test on fresh shot streams."""
import argparse
import csv
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np

from native_memory import make_native_memory
from likelihood_decoder import FaultLikelihoodDecoder
from qec_analysis import matcher, noise_model, wilson

NAMES=("plain","correlated","likelihood","local_likelihood")
ROUNDS=(2,3,5,8,12,16,25,50)
ROOT=Path("results/optimization")


def evaluate(job):
    d,b,profile,assumed,p,r,schedule,n,seed=job
    c=make_native_memory(d,r,b,schedule,p,profile)
    prior = c if assumed==profile else make_native_memory(d,r,b,schedule,p,assumed)
    models=[matcher(prior,"plain"),matcher(prior,"correlated"),FaultLikelihoodDecoder(prior),
            FaultLikelihoodDecoder(prior,split_temporally=True)]
    sampler=c.compile_detector_sampler(seed=seed)
    patterns=np.zeros(16,dtype=np.int64)
    for step in range(0,n,4096):
        det,obs=sampler.sample(min(n-step,4096),separate_observables=True)
        bits=np.zeros(len(det),dtype=np.uint8)
        for i,m in enumerate(models):
            pred=m.decode_batch(det,**({"enable_correlations":True} if i==1 else {}))
            bits |= ((pred[:,0]!=obs[:,0]).astype(np.uint8)<<i)
        patterns+=np.bincount(bits,minlength=16)
    row=dict(distance=d,basis=b,profile=profile,assumed=assumed,p=p,rounds=r,schedule=schedule,
             shots=n,seed=seed)
    for i,name in enumerate(NAMES):
        row[name]=int(sum(patterns[j] for j in range(16) if (j>>i)&1))
    return dict(row,**{f"mask_{i}":int(k) for i,k in enumerate(patterns)})


def save_trials(jobs,path,workers):
    with ProcessPoolExecutor(max_workers=workers) as pool, path.open("w",newline="") as f:
        for j,row in enumerate(pool.map(evaluate,jobs)):
            if j==0:
                writer=csv.DictWriter(f,fieldnames=row)
                writer.writeheader()
            writer.writerow(row)
            f.flush()


def starter_comparison():
    """Anchor the optimized circuits to the four p values in the original demonstration."""
    from raw_stim_d3_surface_code import build_circuit
    from surface_code import make_stim_circuit

    config=json.loads((ROOT/"final_choice.json").read_text())
    rows=[]
    for p in (.001,.003,.005,.01):
        models=[
            ("starter_reset_CX",build_circuit(p,3),"plain"),
            ("no_reset_CX",make_stim_circuit(3,3,"Z",noise=noise_model(p,"uniform")),"plain"),
            ("no_reset_CZ_reference",make_native_memory(3,3,"Z","forward",p),"plain"),
            ("no_reset_CZ_selected",make_native_memory(3,3,"Z",config["schedule"],p),config["selected_decoder"]),
        ]
        for label,circuit,name in models:
            decoder=(FaultLikelihoodDecoder(circuit,split_temporally=name=="local_likelihood")
                     if name in ("likelihood","local_likelihood") else matcher(circuit,name))
            shots=200000
            seed=7903501+len(rows)
            sampler=circuit.compile_detector_sampler(seed=seed)
            errors=0
            for start in range(0,shots,10000):
                det,obs=sampler.sample(min(10000,shots-start),separate_observables=True)
                kw={"enable_correlations":True} if name=="correlated" else {}
                errors+=int((decoder.decode_batch(det,**kw)!=obs).any(axis=1).sum())
            lo,hi=wilson(errors,shots)
            rows.append(dict(p=p,rounds=3,basis="Z",distance=3,model=label,decoder=name,
                             seed=seed,shots=shots,errors=errors,probability=errors/shots,low95=lo,high95=hi))
    with (ROOT/"starter_comparison.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def main(workers):
    ROOT.mkdir(parents=True,exist_ok=True)
    cases=list(itertools.product(ROUNDS,("forward","alternating")))
    # Independent exploratory sample; freeze one schedule and one decoder before final draws.
    pilots=[(3,"Z","balanced","balanced",.003,r,s,50000,189345+i) for i,(r,s) in enumerate(cases)]
    save_trials(pilots,ROOT/"four_decoder_selection.csv",workers)
    with (ROOT/"four_decoder_selection.csv").open() as f:
        pilot=list(csv.DictReader(f))
    scores=[(sum(int(v[name]) for v in pilot if v["schedule"]==s),s,name) for s,name in
            itertools.product(("forward","alternating"),NAMES)]
    k,schedule,name=min(scores)
    config=dict(distance=3,basis="Z",p=.003,profile="balanced",rounds=ROUNDS,
                noise_model="native",schedule=schedule,selected_decoder=name,selection_errors=k,
                selection_shots=50000*len(ROUNDS),scores=scores)
    (ROOT/"final_choice.json").write_text(json.dumps(config,indent=2))
    print("Locked finalist",schedule,name,flush=True)
    final=[(3,"Z","balanced","balanced",.003,r,s,100000,590214+i) for i,(r,s) in enumerate(cases)]
    save_trials(final,ROOT/"four_decoder_final.csv",workers)
    # Compare robustness to a mismatched decoder prior on identical physical data
    # using the same seed and sampling batches for each assumed profile.
    jobs=[]
    for i,(b,p,r,profile) in enumerate(itertools.product("ZX",(.001,.003,.01),(3,12,25),("idle","phase","readout"))):
        for assumed in (profile,"balanced"):
            jobs.append((3,b,profile,assumed,p,r,schedule,4000,976412+i))
    save_trials(jobs,ROOT/"noise_mismatch.csv",workers)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers",type=int,default=4)
    mode=ap.add_mutually_exclusive_group()
    mode.add_argument("--extend-grid",action="store_true",help="Replay the selected schedule's entire screen with the fourth decoder.")
    mode.add_argument("--starter-comparison",action="store_true",help="Run the original 3-round benchmark and no-reset comparisons at each starter p.")
    for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
        os.environ[key]="1"
    args=ap.parse_args()
    if args.starter_comparison:
        starter_comparison()
    elif args.extend_grid:
        config=json.loads((ROOT/"final_choice.json").read_text())
        with (ROOT/"screen.csv").open() as f:
            jobs=[(int(v["distance"]),v["basis"],v["profile"],v["profile"],float(v["p"]),
                   int(v["rounds"]),v["schedule"],int(v["shots"]),int(v["seed"]))
                  for v in csv.DictReader(f) if v["schedule"]==config["schedule"]]
        save_trials(jobs,ROOT/"four_decoder_grid.csv",args.workers)
    else:
        main(args.workers)
