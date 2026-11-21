"""Matched gate-twirling experiment on Emerald using either Qiskit or Qrisp compilation."""
import argparse
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import sys
from uuid import UUID

import numpy as np
from iqm.error_reduction_tools.twirling.twirling_modifiers import TrackingRegisters, process_cz_gate, process_r_gate
from iqm.error_reduction_tools.utils.circuit_utils import TwirledCircuit
from iqm.iqm_client import CircuitCompilationOptions, DDMode
from iqm.pulse import Circuit, CircuitOperation
from iqm.qiskit_iqm.qiskit_to_iqm import MeasurementKey, serialize_instructions

from compare_peer import our_si1000, save
from investigate_translation import audit
from native_memory import make_native_memory
from qec_analysis import fit_rate
from run_on_hardware import connect, prepare

REFERENCE = Path(__file__).resolve().parent/"results/project_comparison/20261121T200524815997Z/settings.json"
SHOTS = 200
INSTANCES = 20
SEED = 22112026


def compile_qrisp(clean, backend, wire_names):
    from qrisp import QuantumCircuit, PassManager
    from qrisp.circuit.pass_management.passes import convert_to_prx
    from iqm.qrisp_iqm import commute_phases, qrisp_to_iqm_converter

    dqa = backend.architecture
    wires = dict(zip(sorted(clean.get_final_qubit_coordinates()), [dqa.qubits.index(q) for q in wire_names], strict=True))
    qc = QuantumCircuit(len(dqa.qubits), clean.num_measurements)
    record = 0
    barrier = False
    for op in clean:
        if op.name in ("DETECTOR","QUBIT_COORDS","OBSERVABLE_INCLUDE","R"):
            continue
        if op.name == "TICK":
            if not barrier:
                qc.barrier([qc.qubits[i] for i in wires.values()])
            barrier = True
            continue
        barrier = False
        qs = [wires[t.value] for t in op.targets_copy()]
        if op.name == "H":
            for q in qs:
                qc.h(q)
        elif op.name == "CZ":
            for a,b in zip(qs[::2],qs[1::2]):
                qc.cz(a,b)
        elif op.name == "M":
            for q in qs:
                qc.measure(q,record)
                record += 1
        else:
            raise ValueError(op.name)
    pm = PassManager()
    pm += commute_phases(False)
    pm += convert_to_prx
    compiled = pm.run(qc)
    # A global phase is unobservable, including during repeated projective readout.
    compiled.data = [inst for inst in compiled.data if inst.op.name != "gphase"]
    ops = qrisp_to_iqm_converter(compiled,dqa).instructions
    normalized = []
    for op in ops:
        if op.name == "measure":
            idx = int(op.args["key"].removeprefix("cb_"))
            op = CircuitOperation("measure",op.locus,{"key":str(MeasurementKey("c",record,0,idx))})
        normalized.append(op)
    return normalized


def pmpt(base,seed):
    # Force the bit frame to I at every readout, including each reused ancilla.
    last = {}
    close_frame = set()
    for i,op in enumerate(base):
        if op.name == "prx":
            last[op.locus[0]] = i
        if op.name == "measure" and op.locus[0] in last:
            close_frame.add(last.pop(op.locus[0]))
    rng = np.random.default_rng(seed)
    regs = TrackingRegisters()
    out = []
    for i,op in enumerate(base):
        gate = TwirledCircuit([])
        if op.name == "prx":
            process_r_gate(op,gate,rng,regs,"I" if i in close_frame else None,fix_axes=True)
        elif op.name == "cz":
            process_cz_gate(op,gate,regs)
        else:
            if op.name == "measure" and regs.extra_pi.get(op.locus[0],0)%2:
                raise ValueError("Unclosed bit frame")
            if op.name not in ("measure","barrier"):
                raise ValueError(op.name)
            out.append(op)
            continue
        out.extend(gate.operations)
    return out


def payload(ops):
    return [dict(name=op.name,locus=op.locus,args=op.args) for op in ops]


def run(args):
    from qec import NoiseModel
    from qec.decode import decode
    if args.submit:
        backend = connect(use_metrics=False)
    else:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        backend = IQMFakeAphrodite()
    layout = json.loads(REFERENCE.read_text())["physical_layouts"]["ours"]
    names = {i:backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
    wire_names = [names[i] for i in layout]
    folder = args.output/args.pipeline
    folder.mkdir(exist_ok=True,parents=True)
    settings = dict(pipeline=args.pipeline, live=args.submit, distance=3, basis="Z", rounds=list(range(1,6)),
                    shots_per_arm=SHOTS*INSTANCES, variants=INSTANCES, seed=SEED, dd="standard", wire_names=wire_names,
                    decoder="BP+OSD", prior="SI1000 p=0.01", calibration=str(backend.architecture.calibration_set_id))
    settings_file = folder/"settings.json"
    if settings_file.exists() and json.loads(settings_file.read_text()) != settings:
        raise ValueError("Use a new output directory for a different calibration or setup")
    save(settings_file,settings)
    summary = []
    for r in range(1,6):
        label = f"r{r}"
        clean = make_native_memory(3,r,"Z","alternating")
        model = our_si1000(clean,NoiseModel.si1000(.01))
        model.to_file(str(folder/(label+".stim")))
        if args.pipeline == "qrisp":
            base = compile_qrisp(clean,backend,wire_names)
        else:
            _,qc,_ = prepare(3,r,"Z",backend,noise_family="native",schedule="alternating",fixed_layout=layout,preserve_ticks=True)
            base = list(serialize_instructions(qc,names))
        base_check = audit(clean,base,wire_names)
        if base_check["cz_or_measures_listed_after_a_later_layer"] or base_check["native_operations"]["cz"] != 24*r:
            raise ValueError("Original layer sequence changed")
        plan = []
        transformed = []
        for i in range(INSTANCES):
            twirl = pmpt(base,SEED+100*r+i)
            check = audit(clean,twirl,wire_names)
            if check != base_check:
                raise ValueError("Gate counts, ordered layers or parity constraints changed")
            digest = hashlib.sha256(json.dumps(payload(twirl),sort_keys=True).encode()).hexdigest()
            transformed.append(digest)
            pair = [("control",base),("twirl",twirl)]
            if (i+r)%2:
                pair.reverse()
            for arm,ops in pair:
                plan.append((arm,i,Circuit(name=f"{args.pipeline}-{label}-{arm}-{i}",instructions=tuple(ops))))
        if len(set(transformed)) != INSTANCES:
            raise ValueError("Duplicate variants")
        save(folder/(label+"-audit.json"),dict(check=base_check,base=payload(base),twirl_sha256=transformed,
                                               manifest=[(arm,i) for arm,i,_ in plan]))
        print(args.pipeline,r,"passed all ideal audits",flush=True)
        if not args.submit:
            continue
        job_path = folder/(label+"-job.json")
        raw_path = folder/(label+"-raw.npz")
        if not raw_path.exists():
            if job_path.exists():
                job = backend.client.get_job(UUID(json.loads(job_path.read_text())["id"]))
            else:
                job = backend.client.submit_circuits([c for _,_,c in plan],shots=SHOTS,
                    calibration_set_id=backend.architecture.calibration_set_id,
                    options=CircuitCompilationOptions(dd_mode=DDMode.ENABLED))
                save(job_path,dict(id=str(job.job_id)))
                print("submitted",r,job.job_id,flush=True)
            job.wait_for_completion(timeout_secs=3600)
            results = job.result()
            if results is None or len(results) != len(plan):
                raise RuntimeError(f"IQM returned {job.status}: {job.data.messages}")
            records = []
            for result in results:
                keys = sorted(result,key=lambda key:MeasurementKey.from_string(key).clbit_idx)
                if [MeasurementKey.from_string(k).clbit_idx for k in keys] != list(range(clean.num_measurements)):
                    raise ValueError("Measurement keys differ")
                records.append(np.column_stack([np.asarray(result[k]).reshape(SHOTS) for k in keys]))
            np.savez_compressed(raw_path,records=np.asarray(records,dtype=bool))
        records = np.load(raw_path)["records"]
        conv = model.compile_m2d_converter()
        blocks=[]
        for (arm,i,_),raw in zip(plan,records,strict=True):
            det,obs = conv.convert(measurements=raw,separate_observables=True)
            blocks.append(dict(arm=arm,i=i,errors=int(decode(det,obs,model,"bposd").errors),shots=len(raw)))
        save(folder/(label+"-blocks.json"),blocks)
        row = dict(rounds=r,**{arm:sum(b["errors"] for b in blocks if b["arm"]==arm) for arm in ("twirl","control")})
        summary.append(row)
        print(row,flush=True)
    if summary:
        fits={arm:fit_rate(settings["rounds"],[v[arm] for v in summary],[SHOTS*INSTANCES]*5) for arm in ("control","twirl")}
        save(folder/"summary.json",dict(rows=summary,fits=fits))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline",choices=["qiskit","qrisp"])
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--peer",type=Path,required=True)
    parser.add_argument("--submit",action="store_true")
    args=parser.parse_args()
    sys.path.append(str(args.peer.resolve()))
    logging.disable(logging.WARNING)
    run(args)

