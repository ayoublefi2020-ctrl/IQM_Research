"""Compare an adapted professor starter schedule with the project's two leading circuits."""
import argparse
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

import numpy as np
from iqm.iqm_client import CircuitCompilationOptions, DDMode
from iqm.pulse import Circuit
from iqm.qiskit_iqm.qiskit_to_iqm import MeasurementKey, serialize_instructions

from compare_peer import our_si1000, save
from investigate_translation import audit
from native_memory import make_native_memory
from run_on_hardware import connect, prepare
from twirl_memory import compile_qrisp, pmpt, payload, REFERENCE


def run(args):
    from qec import NoiseModel
    from qec.decode import decode
    if args.submit:
        backend = connect(use_metrics=False)
    else:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        backend = IQMFakeAphrodite()
    layout = json.loads(REFERENCE.read_text())['physical_layouts']['ours']
    names = {i: backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
    wires = [names[i] for i in layout]
    folder = args.output
    folder.mkdir(parents=True, exist_ok=True)
    settings = dict(distance=3, rounds=[3,5], shots_per_arm=10000, blocks=20, dd='standard',
                    wire_names=wires, live=args.submit, calibration=str(backend.architecture.calibration_set_id),
                    baseline='Professor Stim stabilizer order, adapted to no-reset and native CZ/H',
                    decoder='BP+OSD', prior='SI1000 p=0.01')
    path = folder/'settings.json'
    if path.exists() and json.loads(path.read_text()) != settings:
        raise ValueError('Settings differ from the saved run')
    save(path,settings)
    summaries=[]
    for r in settings['rounds']:
        sources={}
        bases={}
        for name,schedule in [('starter','forward'),('ours_qiskit','alternating')]:
            clean,qc,_=prepare(3,r,'Z',backend,noise_family='native',schedule=schedule,
                               fixed_layout=layout,preserve_ticks=True)
            sources[name]=clean
            bases[name]=list(serialize_instructions(qc,names))
        sources['ours_qrisp_twirl']=sources['ours_qiskit']
        bases['ours_qrisp_twirl']=compile_qrisp(sources['ours_qiskit'],backend,wires)
        checks={name:audit(sources[name],ops,wires) for name,ops in bases.items()}
        for name,check in checks.items():
            h=sum(len(op.targets_copy()) for op in sources[name] if op.name=='H')
            if check['native_operations']['prx']!=h or check['native_operations']['cz']!=24*r:
                raise ValueError(f'{name} model gate count differs from compiled gates')
        plan=[]
        for i in range(20):
            order=list(bases)
            order=order[i%3:]+order[:i%3]
            if i%2: order.reverse()
            for name in order:
                ops=bases[name]
                if name=='ours_qrisp_twirl':
                    ops=pmpt(ops,22112026+100*r+i)
                    assert audit(sources[name],ops,wires)==checks[name]
                plan.append((name,i,Circuit(name=f'{name}-r{r}-{i}',instructions=tuple(ops))))
        save(folder/f'r{r}-audit.json',dict(checks=checks,manifest=[(name,i) for name,i,_ in plan],
                                         bases={name:payload(ops) for name,ops in bases.items()}))
        for name,clean in sources.items():
            our_si1000(clean,NoiseModel.si1000(.01)).to_file(str(folder/f'{name}-r{r}.stim'))
        print('audited',r,{name:c['native_operations'] for name,c in checks.items()},flush=True)
        if not args.submit: continue
        raw_path=folder/f'r{r}-raw.npz'
        job_path=folder/f'r{r}-job.json'
        if not raw_path.exists():
            if job_path.exists():
                job=backend.client.get_job(UUID(json.loads(job_path.read_text())['id']))
            else:
                job=backend.client.submit_circuits([c for _,_,c in plan],shots=500,
                    calibration_set_id=backend.architecture.calibration_set_id,
                    options=CircuitCompilationOptions(dd_mode=DDMode.ENABLED))
                save(job_path,dict(id=str(job.job_id)))
                print('submitted',r,job.job_id,flush=True)
            job.wait_for_completion(timeout_secs=3600)
            result=job.result()
            if result is None or len(result)!=len(plan): raise RuntimeError('Incomplete hardware result')
            raw=[]
            for entry in result:
                keys=sorted(entry,key=lambda k:MeasurementKey.from_string(k).clbit_idx)
                assert [MeasurementKey.from_string(k).clbit_idx for k in keys]==list(range(8*r+9))
                raw.append(np.column_stack([np.asarray(entry[k]).reshape(500) for k in keys]))
            np.savez_compressed(raw_path,records=np.asarray(raw,dtype=bool))
        raw=np.load(raw_path)['records']
        models={name:our_si1000(clean,NoiseModel.si1000(.01)) for name,clean in sources.items()}
        blocks=[]
        for (name,i,_),record in zip(plan,raw,strict=True):
            model=models[name]
            det,obs=model.compile_m2d_converter().convert(measurements=record,separate_observables=True)
            blocks.append(dict(arm=name,i=i,shots=len(record),errors=int(decode(det,obs,model,'bposd').errors)))
        save(folder/f'r{r}-blocks.json',blocks)
        row=dict(rounds=r,**{name:sum(b['errors'] for b in blocks if b['arm']==name) for name in sources})
        summaries.append(row)
        print(row,flush=True)
    if summaries: save(folder/'summary.json',summaries)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--peer',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--submit',action='store_true')
    args=parser.parse_args()
    sys.path.append(str(args.peer.resolve()))
    logging.disable(logging.WARNING)
    run(args)
