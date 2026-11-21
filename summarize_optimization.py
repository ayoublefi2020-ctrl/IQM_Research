"""Summarize the independent confirmation and the exploratory grid, including uncertainty."""
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import chi2,binomtest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from qec_analysis import fit_rate,probability,wilson
from confirm_decoder import NAMES

OUT=Path("results/optimization")


def read(name):
    with (OUT/name).open() as f:
        return list(csv.DictReader(f))


def write(name,rows):
    with (OUT/name).open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def main():
    choice=json.loads((OUT/"final_choice.json").read_text())
    s,name=choice["schedule"],choice["selected_decoder"]
    data=read("four_decoder_final.csv")
    def rows(schedule):
        return sorted([x for x in data if x["schedule"]==schedule],key=lambda x:int(x["rounds"]))
    selected,base=rows(s),rows("forward")
    r=np.array([int(x["rounds"]) for x in selected])
    n=np.array([int(x["shots"]) for x in selected])
    k=np.array([int(x[name]) for x in selected])
    old=np.array([int(x["plain"]) for x in base])
    ps=k/n
    basep=old/n
    difference=(basep-ps).mean()
    # Each stratum has independent baseline and finalist shots, equal weight per round count.
    se=np.sqrt(np.sum((basep*(1-basep)+ps*(1-ps))/(n-1)))/len(n)
    fit=fit_rate(r,k,n)
    fitted=probability(r,fit["rate"])
    dev=sum((k-n*fitted)**2/(n*fitted*(1-fitted)))
    paired={}
    for alternative in NAMES:
        i,j=NAMES.index(alternative),NAMES.index(name)
        masks={m:sum(int(x[f"mask_{m}"]) for x in selected) for m in range(16)}
        a=sum(v for m,v in masks.items() if (m>>i)&1 and not (m>>j)&1)
        b=sum(v for m,v in masks.items() if (m>>j)&1 and not (m>>i)&1)
        paired[alternative]=dict(other_only=a,selected_only=b,p=binomtest(a,a+b).pvalue if a+b else 1.)
    fit_late=fit_rate(r[r>=3],k[r>=3],n[r>=3])
    summary=dict(target=s,decoder=name,reference_errors=int(sum(old)),finalist_errors=int(sum(k)),
                 shots_per_candidate=int(sum(n)),relative_reduction=float(1-ps.mean()/basep.mean()),
                 mean_difference=difference,difference_ci95=[difference-1.96*se,difference+1.96*se],
                 fit_all=fit,fit_from_round3=fit_late,pearson_chi2=dev,fit_df=len(n)-1,
                 fit_gof_p=chi2.sf(dev,len(n)-1),paired=paired)
    cases=defaultdict(lambda:dict(shots=0,plain=0,correlated=0,likelihood=0))
    columns=("distance","basis","profile","p","rounds","schedule")
    replay={}
    for x in read("screen.csv"):
        key=tuple(x[col] for col in columns)
        for col in cases[key]:
            cases[key][col]+=int(x[col])
        if x["schedule"]==s:
            replay[key+(x["seed"],)]=x
    for x in read("four_decoder_grid.csv"):
        key=tuple(x[col] for col in columns)
        source=replay.pop(key+(x["seed"],))
        if any(x[col]!=source[col] for col in ("shots","plain","correlated","likelihood")):
            raise ValueError(f"Screen replay differs at {key}, seed {x['seed']}")
        cases[key]["local_likelihood"]=cases[key].get("local_likelihood",0)+int(x["local_likelihood"])
    if replay:
        raise ValueError("Selected schedule has missing four-decoder rows")
    same_schedule=[values for key,values in cases.items() if key[-1]==s]
    summary["broad_screen_on_selected_schedule"]={col:sum(v[col] for v in same_schedule)
                                                  for col in ("shots",*NAMES)}
    summary["target_by_round"]=[dict(rounds=int(a),shots_per_candidate=int(b),reference_errors=int(c),
                                     finalist_errors=int(d)) for a,b,c,d in zip(r,n,old,k)]
    table=[]
    for (d,b,prof,p,rounds,sch),v in cases.items():
        for method in (m for m in NAMES if m in v):
            count,total=v[method],v["shots"]
            lo,hi=wilson(count,total)
            table.append(dict(distance=d,basis=b,profile=prof,p=p,rounds=rounds,schedule=sch,
                              decoder=method,shots=total,failures=count,prob=count/total,low95=lo,high95=hi))
    write("screen_intervals.csv",table)
    byprofile={}
    for x in read("noise_mismatch.csv"):
        key=(x["profile"],"matched" if x["profile"]==x["assumed"] else "balanced")
        v=byprofile.setdefault(key,dict(shots=0,errors=0))
        v["shots"]+=int(x["shots"])
        v["errors"]+=int(x[name])
    summary["mismatch_for_finalist"]={a+"_"+b:v for (a,b),v in byprofile.items()}
    (OUT/"outcomes.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    fig,(ax,noise_ax)=plt.subplots(1,2,figsize=(11,4.3),layout="constrained")
    for label,series,mark in [("Forward + ordinary matching",old,"s"),("Selected circuit and decoder",k,"o")]:
        bounds=np.asarray([wilson(e,t) for e,t in zip(series,n)])
        y=series/n
        ax.errorbar(r,100*y,yerr=100*np.maximum(0,[y-bounds[:,0],bounds[:,1]-y]),fmt=mark+"-",capsize=3,label=label)
    ax.set(xlabel="Stabilizer rounds",ylabel="Logical failures (%)",title="Independent target test at p = 0.003")
    ax.legend(fontsize=8)
    for prof in ("balanced","idle","readout","phase"):
        sub=sorted([x for x in table if x["distance"]=="3" and x["basis"]=="Z" and x["profile"]==prof
                    and x["rounds"]=="12" and x["schedule"]==s and x["decoder"]==name],key=lambda x:float(x["p"]))
        y=np.array([x["prob"] for x in sub])
        bounds=np.array([(x["low95"],x["high95"]) for x in sub])
        noise_ax.errorbar([100*float(x["p"]) for x in sub],100*y,
                          yerr=100*np.maximum(0,[y-bounds[:,0],bounds[:,1]-y]),fmt="o-",capsize=2,label=prof)
    noise_ax.set(xscale="log",xlabel="CZ depolarization parameter p (%)",ylabel="Logical failures (%)",
                 title="Selected decoder at 12 rounds, distance-3 Z")
    noise_ax.legend(fontsize=8)
    for a in (ax,noise_ax):
        a.grid(alpha=.2)
    fig.savefig(OUT/"performance.png",dpi=170)
    plt.close(fig)


if __name__=="__main__":
    main()
