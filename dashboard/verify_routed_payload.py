import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import stim
from qiskit.circuit.library import RGate
from iqm.qiskit_iqm.qiskit_to_iqm import MeasurementKey
from native_memory import make_native_memory

def routed_model(clean, operations, *, cz_error=0., rotation_error=0., readout_error=0.):
    """Replay the submitted Clifford instructions and their original measurement keys."""
    native=stim.Circuit()
    wires={}
    records={}
    rotations={}
    for op in operations:
        name,locus,args=op["name"],op["locus"],op["args"]
        if name=="barrier":
            continue
        qs=[wires.setdefault(q,len(wires)) for q in locus]
        if name=="prx":
            angles=(args["angle"],args["phase"])
            if angles not in rotations:
                rotations[angles]=stim.Tableau.from_unitary_matrix(RGate(*angles).to_matrix(),endian="little").to_circuit()
            for gate in rotations[angles]:
                native.append(gate.name,qs*len(gate.targets_copy()))
            if rotation_error:
                native.append("DEPOLARIZE1",qs,rotation_error)
        elif name=="cz":
            native.append("CZ",qs)
            if cz_error:
                native.append("DEPOLARIZE2",qs,cz_error)
        elif name=="measure":
            key=MeasurementKey.from_string(args["key"]).clbit_idx
            if key in records:
                raise ValueError(f"Duplicate measurement key {key}")
            records[key]=len(records)
            native.append("M",qs,readout_error)
        else:
            raise ValueError(f"Unknown native operation {name}")
    n=clean.num_measurements
    if sorted(records)!=list(range(n)):
        raise ValueError("Native measurement keys do not cover the ideal record")
    measured=0
    for op in clean:
        if op.name=="M":
            measured+=len(op.targets_copy())
        elif op.name in ("DETECTOR","OBSERVABLE_INCLUDE"):
            targets=[stim.target_rec(records[measured+t.value]-n) for t in op.targets_copy()]
            native.append(op.name,targets,op.gate_args_copy())
    return native,records,wires

def verify_payload(clean, operations):
    native,records,wires=routed_model(clean,operations)
    n=clean.num_measurements
    native.detector_error_model()
    assert native.count_determined_measurements()==clean.count_determined_measurements()
    record=native.reference_sample()[[records[i] for i in range(n)]].reshape(1,-1)
    det,obs=clean.compile_m2d_converter().convert(measurements=record,separate_observables=True)
    assert not det.any() and not obs.any()
    return dict(ideal_measurement_distribution_matches=True,measurement_keys=n,independent_parities=native.count_determined_measurements(),
                physical_wires=len(wires))

if __name__=="__main__":
    path=Path("research_data/distance_5/routed_hardware")
    result=verify_payload(make_native_memory(5,3,"Z","alternating"),json.loads((path/"instructions.json").read_text()))
    (path/"payload_verification.json").write_text(json.dumps(result,indent=2))
    print(result)
