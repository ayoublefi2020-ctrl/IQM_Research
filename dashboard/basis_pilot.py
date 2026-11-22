"""Matched distance-3 X/Z pilot, one IQM job. Re-running collects the saved ID."""
import json
import sys
from pathlib import Path
from uuid import UUID

import numpy as np
import stim
from iqm.iqm_client import CircuitCompilationOptions, DDMode
from iqm.pulse import Circuit
from iqm.qiskit_iqm.qiskit_to_iqm import MeasurementKey, serialize_instructions

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_memory import make_native_memory
from run_on_hardware import connect, prepare, decode_hardware_results
from verify_routed_payload import verify_payload

DEST = ROOT / "research_data/distance_3/basis_pilot"
SHOTS = 1000


def save(name, data):
    path = DEST / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def run():
    DEST.mkdir(parents=True, exist_ok=True)
    if (DEST / "decoded.json").exists():
        return
    backend = connect(use_metrics=False)
    job_path = DEST / "job.json"
    if job_path.exists():
        meta = json.loads(job_path.read_text())
        job = backend.client.get_job(UUID(meta["job"]))
    else:
        topology = json.loads((ROOT / "research_data/hardware_characterization/topology.json").read_text())
        layout = topology["distances"]["3"]["layout"]
        names = {i: backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
        circuits = []
        audits = {}
        for basis in ("X", "Z"):
            clean, native, audit = prepare(3, 3, basis, backend, noise_family="native", schedule="alternating",
                                          fixed_layout=layout, preserve_ticks=True)
            ops = serialize_instructions(native, names)
            payload = [dict(name=o.name, args=o.args, locus=o.locus) for o in ops]
            audit.update(verify_payload(clean, payload), swaps=0)
            audits[basis] = audit
            save(f"{basis}-instructions.json", payload)
            make_native_memory(3, 3, basis, "alternating", p=.003).to_file(str(DEST / f"{basis}.stim"))
            circuits.append(Circuit(name=f"QuantumTN-d3-{basis}-r3", instructions=tuple(ops)))
        calibration = backend.architecture.calibration_set_id
        job = backend.client.submit_circuits(circuits, shots=SHOTS, calibration_set_id=calibration,
                    options=CircuitCompilationOptions(dd_mode=DDMode.ENABLED))
        meta = dict(job=str(job.job_id), calibration=str(calibration), audits=audits, bases=["X", "Z"],
                    shots=SHOTS, rounds=3, decoder="correlated", p=.003, dd="standard",
                    twirling=False, wire_names=[names[i] for i in layout])
        save("job.json", meta)
    print("Pilot job", job.job_id, flush=True)
    job.wait_for_completion(timeout_secs=300)
    response = job.result()
    if response is None:
        print("IQM status", job.status, flush=True)
        return
    if len(response) != len(meta["bases"]):
        raise ValueError("Unexpected circuit count")
    rows = {}
    for basis, result in zip(meta["bases"], response, strict=True):
        model = stim.Circuit.from_file(str(DEST / f"{basis}.stim"))
        columns = {MeasurementKey.from_string(k).clbit_idx: np.asarray(v) for k, v in result.items()}
        if len(columns) != len(result) or sorted(columns) != list(range(model.num_measurements)):
            raise ValueError("IQM measurement keys differ from the circuit")
        raw = np.column_stack([columns[i].reshape(meta["shots"]) for i in range(len(columns))])
        if not np.isin(raw, [0, 1]).all():
            raise ValueError("Nonbinary readout")
        raw = raw.astype(bool)
        np.savez_compressed(DEST / f"{basis}-raw.npz", records=raw)
        det, obs = model.compile_m2d_converter().convert(measurements=raw, separate_observables=True)
        rows[basis] = decode_hardware_results(dict(det_events=det, obs_flips=obs), model, meta["decoder"])
    save("decoded.json", rows)
    print(rows)
    from import_data import write_database
    write_database()


if __name__ == "__main__":
    run()
