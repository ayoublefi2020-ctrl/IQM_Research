"""Screen three CZ schedules and three decoders, select on target shots, then validate."""
import argparse
import csv
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from likelihood_decoder import FaultLikelihoodDecoder
from native_memory import PROFILES, SCHEDULES, make_native_memory
from qec_analysis import matcher

DECODERS = ("plain", "correlated", "likelihood")
ROUNDS = (1,2,3,4,5,8,12,16,25,50)
STRENGTHS = (.0005,.001,.002,.003,.005,.01,.02)
TARGET_ROUNDS = (2,3,5,8,12,16,25,50)
DIRECTORY = Path("results/optimization")


def configurations(phase):
    if phase == "screen":
        yield from itertools.product((3,), "ZX", PROFILES, STRENGTHS, ROUNDS)
        yield from itertools.product((5,), "ZX", PROFILES, (.001,.003,.01), (3,8,16,25))
        yield from itertools.product((7,), "ZX", ("balanced",), (.003,.01), (3,8,16))
    else:
        yield from itertools.product((3,), "Z", ("balanced",), (.003,), TARGET_ROUNDS)


def trial(parameters):
    phase, condition, schedule, seed, shots = parameters
    d,b,profile,p,r = condition
    c = make_native_memory(d,r,b,schedule,p,profile)
    ref = c.without_noise()
    models = [matcher(c,"plain"), matcher(c,"correlated"), FaultLikelihoodDecoder(c)]
    sampler = c.compile_detector_sampler(seed=seed)
    counts = np.zeros(8,dtype=np.int64)
    detector_events = 0
    for start in range(0, shots, 4096):
        events,obs = sampler.sample(min(4096,shots-start), separate_observables=True)
        detector_events += int(events.sum())
        signature = np.zeros(len(events),dtype=np.uint8)
        for i,name in enumerate(DECODERS):
            kwargs = {"enable_correlations":True} if name=="correlated" else {}
            prediction = models[i].decode_batch(events,**kwargs)
            signature |= ((prediction[:,0]!=obs[:,0]).astype(np.uint8) << i)
        counts += np.bincount(signature,minlength=8)
    row = dict(phase=phase,distance=d,basis=b,profile=profile,p=p,rounds=r,schedule=schedule,
               shots=shots,seed=seed,detector_fraction=detector_events/(shots*c.num_detectors),
               h_gates=sum(len(op.targets_copy()) for op in ref if op.name=="H"),
               cz_gates=sum(len(op.targets_copy())//2 for op in ref if op.name=="CZ"))
    for i,name in enumerate(DECODERS):
        row[name]=int(sum(counts[j] for j in range(8) if j & (1<<i)))
    row.update({f"pattern_{i}": int(n) for i,n in enumerate(counts)})
    return row


def run_phase(phase, args):
    ids = {"screen":1,"selection":2,"validation":3,"confirmation":4}
    jobs = []
    for i,condition in enumerate(configurations(phase)):
        for j,schedule in enumerate(SCHEDULES):
            if phase=="confirmation" and schedule=="literal":
                continue
            for rep in range(args.repeats):
                seed = int(np.random.SeedSequence([args.seed,ids[phase],i,j,rep]).generate_state(1,dtype=np.uint64)[0])
                n = args.screen_shots if phase=="screen" else args.target_shots
                jobs.append((phase,condition,schedule,seed,n))
    with ProcessPoolExecutor(max_workers=args.workers) as workers, (args.output/(phase+".csv")).open("w",newline="") as f:
        rows = workers.map(trial,jobs,chunksize=1)
        for i,row in enumerate(rows):
            if i==0:
                writer = csv.DictWriter(f,fieldnames=row)
                writer.writeheader()
            writer.writerow(row)
            if (i+1)%100==0:
                f.flush()
                print(phase,i+1,"/",len(jobs),flush=True)
    print(phase,"complete:",len(jobs),"batches",flush=True)


def choose(args):
    with (args.output/"selection.csv").open() as f:
        rows=list(csv.DictReader(f))
    scores = []
    for schedule,decoder in itertools.product(SCHEDULES, DECODERS):
        group = [row for row in rows if row["schedule"]==schedule]
        errors=sum(int(row[decoder]) for row in group)
        total=sum(int(row["shots"]) for row in group)
        scores.append(dict(schedule=schedule,decoder=decoder,errors=errors,shots=total))
    best=min(scores,key=lambda v:v["errors"]/v["shots"])
    choice=dict(schedule=best["schedule"],selected_decoder=best["decoder"],noise_model="native",
                profile="balanced",p=.003,distance=3,basis="Z",rounds=TARGET_ROUNDS,
                selection_scores=scores)
    # The physical schedule stays fixed. A decoder can be chosen offline for
    # each circuit length using selection shots alone.
    choice["decoder_by_round"] = {}
    for r in TARGET_ROUNDS:
        group = [row for row in rows if row["schedule"]==best["schedule"] and int(row["rounds"])==r]
        choice["decoder_by_round"][str(r)] = min(DECODERS,key=lambda name:sum(int(row[name]) for row in group))
    (args.output/"hardware_choice.json").write_text(json.dumps(choice,indent=2))
    print("Selected on independent target selection data:",best,flush=True)


if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phases",nargs="+",choices=("screen","selection","validation","confirmation"),default=["screen","selection","validation"])
    ap.add_argument("--output",type=Path,default=DIRECTORY)
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--repeats",type=int,default=2)
    ap.add_argument("--screen-shots",type=int,default=1000)
    ap.add_argument("--target-shots",type=int,default=30000)
    ap.add_argument("--seed",type=int,default=451731)
    args=ap.parse_args()
    if min(args.screen_shots,args.target_shots,args.workers,args.repeats)<1:
        ap.error("Shot counts, repeats and workers must be positive")
    args.output.mkdir(exist_ok=True,parents=True)
    for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
        os.environ[key]="1"
    for phase in args.phases:
        if phase in ("validation","confirmation") and not (args.output/"hardware_choice.json").exists():
            ap.error("Run the selection phase first to lock the comparison.")
        (args.output/(phase+"_settings.json")).write_text(json.dumps(dict(vars(args),output=str(args.output)),indent=2))
        run_phase(phase,args)
        if phase=="selection":
            choose(args)
