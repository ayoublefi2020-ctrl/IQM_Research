import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import PercentFormatter
p=Path('results/twirl_emerald_20261122')
out=Path('output/pdf')
def read(f): return json.loads(f.read_text())
comp=read(p/'comparison.json')
rng=np.random.default_rng(211)
names=['qiskit','qrisp']
colors=['#255BA3','#C15326']
rounds=np.arange(1,6)
data={}
cost={}
for n in names:
    data[n]=[]
    cost[n]=[]
    for r in rounds:
        a=read(p/n/f'r{r}-audit.json')
        ops=a['check']['native_operations']
        depth={}
        for op in a['base']:
            wires=op['locus']
            level=max(depth.get(q,0) for q in wires)+int(op['name']!='barrier')
            depth.update(dict.fromkeys(wires,level))
        cost[n].append([ops['prx'],ops['cz'],ops['measure'],max(depth.values())])
        b=read(p/n/f'r{r}-blocks.json')
        vals=np.array([[x['errors'] for x in sorted(b,key=lambda x:x['i']) if x['arm']==arm] for arm in ['control','twirl']])
        assert vals.shape==(2,20) and all(x['shots']==200 for x in b)
        assert list(vals.sum(1))==[c[r-1] for c in comp[n]['counts']]
        ix=rng.integers(0,20,(20000,20))
        diff=(vals[0]-vals[1])/2
        data[n].append([diff.mean(),*np.percentile(diff[ix].mean(1),[2.5,97.5])])
print(cost,data)
plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#243849','text.color':'#193046','axes.titlecolor':'#193046','axes.edgecolor':'#9AABB4','font.family':'DejaVu Sans','pdf.fonttype':42})
def page(title,sub,num):
    f=plt.figure(figsize=(11.7,8.3),facecolor='white')
    f.text(.075,.936,'QUANTUM ERROR CORRECTION   /   IQM EMERALD',color='#2E7468',size=11,weight='bold')
    f.text(.075,.858,title,size=28,weight='bold')
    f.text(.075,.805,sub,size=13)
    f.text(.075,.045,'Distance-3 Z memory   /   22 November 2026',size=10,color='#547078')
    f.text(.926,.045,f'{num} / 3',ha='right',size=10,color='#547078')
    return f
def grid(ax):
    ax.grid(axis='y',color='#DDE6E9'); ax.set_axisbelow(True)
def export(f,slug):
    pdf.savefig(f)
    f.savefig(out/(slug+'.png'),dpi=180)
    plt.close(f)
with PdfPages(out/'Emerald-gate-twirling-analysis.pdf') as pdf:
    f=page('How often did the logical memory fail?','Decoded failures per 4,000 shots, for circuits ending after one to five stabilizer rounds.',1)
    for i,n in enumerate(names):
        ax=f.add_axes([.083+.467*i,.265,.388,.44])
        ax.set_title(['Qiskit','Qrisp'][i],loc='left',weight='bold')
        for j,label in enumerate(['Control','Gate twirling']):
            y=np.array(comp[n]['counts'][j])/40
            ax.plot(rounds,y,marker=['o','D'][j],ls=['--','-'][j],color=['#626F80',colors[i]][j],lw=2.2,label=label)
        ax.set(xticks=rounds,ylim=(0,12),yticks=np.arange(0,13,2),xlabel='Stabilizer rounds')
        ax.yaxis.set_major_formatter(PercentFormatter(100,0))
        if i==0: ax.set_ylabel('Logical failure probability')
        grid(ax); ax.legend(loc='upper left',frameon=False,fontsize=10)
    f.text(.075,.155,'At three rounds, Qrisp with twirling had the fewest failures (208 of 4,000). At five rounds, both twirled',size=13)
    f.text(.075,.12,'pipelines recorded 375 failures. Lines connect measured points. Each pipeline ran in separate jobs.',size=13)
    export(f,'logical-error-curves')
    f=page('How much did gate twirling help?','Control failure probability minus twirled failure probability. Positive values favor twirling.',2)
    ax=f.add_axes([.105,.34,.81,.365])
    ax.axhline(0,color='#34485A',lw=1.3)
    for i,n in enumerate(names):
        y,lo,hi=np.array(data[n]).T
        ax.errorbar(rounds+[-.07,.07][i],y,yerr=[y-lo,hi-y],fmt=['o','D'][i],color=colors[i],ms=7,capsize=5,lw=2,label=['Qiskit','Qrisp'][i])
    ax.set(xlim=(.65,5.35),xticks=rounds,xlabel='Stabilizer rounds',ylabel='Reduction (percentage points)')
    ax.legend(frameon=False,ncol=2,loc='upper left');grid(ax)
    f.text(.075,.235,'Qrisp improved at all five lengths. Qiskit worsened at three and four rounds. At five rounds,',size=13)
    f.text(.075,.20,'twirling reduced observed failures by 1.30 percentage points on Qiskit and 0.575 points on Qrisp.',size=13)
    f.text(.075,.128,'Bars show pointwise 95% bootstrap intervals from 20 interleaved pairs of 200-shot blocks per job (20,000 resamples).',size=10.5)
    f.text(.075,.096,'They capture variation within this run. Comparing ten intervals also increases the chance of an apparently large effect.',size=10.5)
    export(f,'twirling-effect')
    f=page('What changed as the circuit grew?','Each extra round added 28 single-qubit rotations, 24 CZ gates and eight measurements.',3)
    headers=['Rounds','PRX','CZ','Readouts','Depth (Qiskit / Qrisp)']
    rows=[[str(r),*map(str,cost['qiskit'][r-1][:3]),f"{cost['qiskit'][r-1][3]} / {cost['qrisp'][r-1][3]}"] for r in rounds]
    ax=f.add_axes([.075,.485,.85,.27]); ax.axis('off')
    t=ax.table(cellText=rows,colLabels=headers,cellLoc='center',colWidths=[.15,.15,.15,.18,.37],bbox=[0,0,1,1]);t.auto_set_font_size(False);t.set_fontsize(12)
    for (row,col),c in t.get_celld().items():
        c.set_edgecolor('white'); c.set_facecolor('#DDEEEA' if row==0 else ['#F2F5F6','white'][row%2])
        if row==0:c.set_text_props(weight='bold')
    f.text(.075,.443,'Depth counts parallel gate and measurement layers in the submitted controls. Barriers synchronize wires at zero cost.',size=10.3)
    f.text(.075,.413,'Physical pulse durations were unavailable. Both pipelines used zero SWAPs and twirling preserved native gate counts.',size=10.3)
    f.text(.075,.342,'Interpreting the per-round error estimate',size=17,weight='bold')
    f.text(.075,.294,'The constant-rate fit fell from 2.04% to 1.96% with Qiskit and from 1.94% to 1.84% with Qrisp.',size=12)
    f.text(.075,.254,'The 95% paired intervals for those reductions include zero (Qiskit -0.11 to +0.27 points, Qrisp -0.07',size=12)
    f.text(.075,.219,'to +0.27). All four fits show lack of fit (Pearson p < 0.001). Use measured errors for a specific length.',size=12)
    f.text(.075,.148,'Fixed across jobs: 17 physical qubits, no reset, standard dynamical decoupling, BP+OSD decoding and SI1000 prior p = 0.01.',size=10.3)
    f.text(.075,.115,'The hardware supplied the noise. Round count and gate exposure grew together, so these data cannot isolate a gate-specific error.',size=10.3)
    export(f,'circuit-resources')
