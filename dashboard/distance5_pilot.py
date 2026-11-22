import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from qiskit import transpile
from qiskit.transpiler import CouplingMap
from qiskit_aer import AerSimulator
from iqm.iqm_client import CircuitCompilationOptions, DDMode
from iqm.pulse import Circuit
from iqm.qiskit_iqm.qiskit_to_iqm import MeasurementKey, serialize_instructions
from native_memory import make_native_memory
from stim_to_qiskit import stim_to_qiskit
from run_on_hardware import connect,process_counts,decode_hardware_results
from qec_analysis import wilson

def save(dest,name,data):
    (dest/name).write_text(json.dumps(data,indent=2),encoding="utf-8")

def run(backend,submit,optimize=False):
    dest=Path("research_data/distance_5")/("routed_hardware" if submit else "routed_compile")
    if optimize:
        dest=dest.with_name("routing_followup" if submit else "routing_followup_fixture")
    dest.mkdir(parents=True,exist_ok=True)
    jobfile=dest/"job-r3.json"
    if jobfile.exists() and (dest/"errors-r3.json").exists():
        print("Existing completed job",json.loads(jobfile.read_text())["job_id"])
        return
    if submit and jobfile.exists():
        from uuid import UUID
        import stim
        saved=json.loads(jobfile.read_text())
        model=stim.Circuit.from_file(str(dest/"decoder-r3.stim"))
        job=backend.client.get_job(UUID(saved["job_id"]))
        return collect(dest,job,model,saved["calibration"],saved["shots"])
    clean=make_native_memory(5,3,"Z","alternating")
    model=make_native_memory(5,3,"Z","alternating",p=.003)
    logical,*_=stim_to_qiskit(clean,preserve_ticks=True)
    edges=[edge for edge in backend.target["cz"] if edge and len(edge)==2]
    coupling=CouplingMap(list({e for a,b in edges for e in ((a,b),(b,a))}))
    trials=[]
    options=dict(coupling_map=coupling,basis_gates=["h","cz","swap"],optimization_level=1)
    if optimize:
        from build_emerald_qubit_rotated import _candidate_layouts
        exact=next(_candidate_layouts(logical,edges,backend.num_qubits,1),None)
    else:
        exact=None
    if exact is not None:
        routed=transpile(logical,**options,initial_layout=exact,routing_method="none",seed_transpiler=19)
    else:
        best=None
        for seed in (range(24) if optimize else [19]):
            candidate=transpile(logical,**options,routing_method="sabre",seed_transpiler=seed)
            score=(int(candidate.count_ops().get("swap",0)),candidate.depth())
            trials.append(dict(seed=seed,swaps=score[0],depth=score[1]))
            if best is None or score<best:
                best,routed=score,candidate
    counts=AerSimulator(method="stabilizer").run(routed,shots=256,seed_simulator=19).result().get_counts()
    syn=process_counts(counts,clean,256)
    if syn["det_events"].any() or syn["obs_flips"].any():
        raise ValueError("Routed circuit failed ideal detector test")
    compiled=transpile(routed,backend=backend,initial_layout=list(range(routed.num_qubits)),routing_method="none",optimization_level=1,seed_transpiler=19)
    names={i:backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
    ops=serialize_instructions(compiled,names)
    from iqm.qiskit_iqm.iqm_circuit_validation import validate_circuit
    validate_circuit(compiled,backend)
    from verify_routed_payload import verify_payload
    instructions=[dict(name=o.name,locus=o.locus,args=o.args) for o in ops]
    verification=verify_payload(clean,instructions)
    shots=1000
    calibration=str(backend.architecture.calibration_set_id)
    meta=dict(distance=5,rounds=3,basis="Z",pipeline="qiskit",source="COMPILATION_ONLY",calibration=calibration,shots=shots,
              swap=int(routed.count_ops().get("swap",0)),native_operations=dict(compiled.count_ops()),depth=compiled.depth(),
              initial_layout=routed.layout.initial_index_layout(filter_ancillas=True),ideal_shots_checked=256)
    save(dest,"compile.json",meta)
    if optimize:
        save(dest,"route_search.json",dict(trials=trials,exact_found=exact is not None,edges=edges))
    save(dest,"instructions.json",instructions)
    save(dest,"payload_verification.json",verification)
    model.to_file(str(dest/"decoder-r3.stim"))
    print(meta,flush=True)
    if not submit:
        return
    if optimize and meta["swap"]>=115:
        print("Retaining offline results. No reduction compared with the original 115 SWAPs.")
        return
    job=backend.client.submit_circuits([Circuit(name="QuantumTN-distance5-r3",instructions=tuple(ops))],shots=shots,
             calibration_set_id=backend.architecture.calibration_set_id,options=CircuitCompilationOptions(dd_mode=DDMode.ENABLED))
    save(dest,"job-r3.json",dict(job_id=str(job.job_id),calibration=calibration,shots=shots))
    collect(dest,job,model,calibration,shots)

def collect(dest,job,model,calibration,shots):
    print("IQM job",job.job_id,flush=True)
    while True:
        status=job.wait_for_completion(timeout_secs=300)
        state=getattr(status,"value",str(status))
        save(dest,"execution.json",dict(job_id=str(job.job_id),status=state))
        print("IQM status",state,flush=True)
        if state=="completed":
            break
        if state in ("failed","cancelled"):
            raise RuntimeError(f"IQM job {job.job_id} ended with status {state}")
    results=job.result()
    if not results:
        raise RuntimeError(f"IQM completed {job.job_id} without returning measurements")
    result=results[0]
    keys=sorted(result,key=lambda key:MeasurementKey.from_string(key).clbit_idx)
    if [MeasurementKey.from_string(key).clbit_idx for key in keys]!=list(range(model.num_measurements)):
        raise ValueError("IQM measurement keys differ")
    raw=np.column_stack([np.asarray(result[k]).reshape(shots) for k in keys]).astype(bool)
    np.savez_compressed(dest/"r3-raw.npz",records=raw)
    det,obs=model.compile_m2d_converter().convert(measurements=raw,separate_observables=True)
    errors=decode_hardware_results(dict(det_events=det,obs_flips=obs),model,"correlated")
    save(dest,"errors-r3.json",dict(errors,job_id=str(job.job_id),calibration=calibration,decoder="correlated",
                                   detector_rates=det.mean(0).tolist()))
    save(dest,"execution.json",dict(job_id=str(job.job_id),status="complete"))
    from import_data import write_database
    write_database()
    print(errors,flush=True)

if __name__=="__main__":
    optimize="--optimize" in sys.argv
    if "--submit" in sys.argv:
        calibration=None
        if optimize:
            calibration=json.loads(Path("research_data/distance_3/basis_pilot/job.json").read_text())["calibration"]
        run(connect(use_metrics=False,calibration_set_id=calibration),True,optimize)
    else:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        run(IQMFakeAphrodite(),False,optimize)
