import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import geometry,simulate
import stim
from native_memory import make_native_memory
from internal_helpers import get_qubit_lists
from qec_analysis import matcher, failures

def verify():
    out=[]
    for d in (3,5):
        geom=geometry(d)
        types={n["id"]:n["type"] for n in geom["nodes"]}
        checks={q:set() for q,k in types.items() if k!="data"}
        for a,b in geom["edges"]:
            anc,data=(a,b) if a in checks else (b,a)
            checks[anc].add(data)
        assert len(checks)==d*d-1
        assert all(len(s&t)%2==0 for a,s in checks.items() for b,t in checks.items() if types[a]!=types[b])
        for basis in "XZ":
            for r in (3,5,20):
                clean=make_native_memory(d,r,basis,"alternating")
                model=make_native_memory(d,r,basis,"alternating",p=.003)
                assert len(model.shortest_graphlike_error())==d
                assert not clean.compile_detector_sampler(seed=3).sample(64,append_observables=True).any()
                if r==3:
                    data,anc=get_qubit_lists(clean)
                    graph=matcher(model,"plain")
                    for faults in ([("X_ERROR",data[0])],[("Y_ERROR",data[0])],[("Z_ERROR",data[0])],
                                   [("X_ERROR",data[0]),("Z_ERROR",data[-1])],[("X_ERROR",anc[0])]):
                        if len(faults)==2 and d==3:
                            continue
                        inj=stim.Circuit()
                        for i,op in enumerate(clean):
                            if op.name=="M" and op.targets_copy()[0].value in anc:
                                for gate,q in faults:
                                    inj.append(gate,[q],1)
                                inj+=clean[i:]
                                break
                            inj.append(op)
                        det,obs=inj.compile_detector_sampler(seed=11).sample(32,separate_observables=True)
                        assert not failures(graph,"plain",det,obs).any(),(d,basis,faults)
                out.append(dict(distance=d,basis=basis,rounds=r,distance_graphlike=d,shots_noiseless=64))
    return out

if __name__=="__main__":
    results=verify()
    path=Path("research_data/distance_5/validation.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(results,indent=2),encoding="utf-8")
    print(f"{len(results)} distance/basis/round configurations verified")
    if "--sweep" in sys.argv:
        for distance in (3,5):
            for profile in ("balanced","readout","idle","phase"):
                for rounds in (3,5,20):
                    result=simulate(dict(distance=distance,basis="Z",rounds=rounds,shots=4000,seed=51226,
                                         profile=profile,decoder="correlated",p=.003,cz=.003,readout=.003,prep=.003,idle=.003))
                    print(distance,profile,rounds,result["failures"],flush=True)
