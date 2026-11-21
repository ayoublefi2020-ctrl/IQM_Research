"""Check the IQM gate stream against the ideal memory, then test layer barriers on the previous patch."""
import argparse
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import stim
from iqm.qiskit_iqm.qiskit_to_iqm import MeasurementKey, serialize_instructions
from qiskit.circuit.library import RGate

from device_noise import mapped_decoder_model
from internal_helpers import get_meas_order
from run_on_hardware import connect, decode_hardware_results, prepare, process_counts

PREVIOUS = Path("results/hardware/20261121T192624300601Z")


def audit(source, instructions, wire_names):
    """Prove agreement of the noiseless Clifford measurement distributions, including bit signs."""
    names = dict(zip(sorted(source.get_final_qubit_coordinates()), wire_names, strict=True))
    wires = {name: i for i, name in enumerate(wire_names)}
    expected_readout = [names[q] for q in get_meas_order(source)]
    native = stim.Circuit()
    key_to_record = {}
    checks = []
    epochs = defaultdict(deque)
    epoch = measured = 0
    for op in source:
        qs = [t.value for t in op.targets_copy()]
        if op.name == "CZ":
            for a, b in zip(qs[::2], qs[1::2]):
                epochs[tuple(sorted((names[a], names[b])))].append(epoch)
        elif op.name == "TICK":
            epoch += 1
        elif op.name == "M":
            for q in qs:
                epochs[("measure", measured)].append(epoch)
                measured += 1
        elif op.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            checks.append((op.name, [measured + t for t in qs], op.gate_args_copy()))

    order = []
    rotations = {}
    for op in instructions:
        qs = [wires[q] for q in op.locus]
        if op.name == "prx":
            angles = (op.args["angle"], op.args["phase"])
            if angles not in rotations:
                matrix = RGate(*angles).to_matrix()
                rotations[angles] = stim.Tableau.from_unitary_matrix(matrix, endian="little").to_circuit()
            for gate in rotations[angles]:
                native.append(gate.name, qs * len(gate.targets_copy()))
        elif op.name == "cz":
            native.append("CZ", qs)
            order.append(epochs[tuple(sorted(op.locus))].popleft())
        elif op.name == "measure":
            key = MeasurementKey.from_string(op.args["key"])
            i = key.clbit_idx
            if key.creg_idx != 0 or key.creg_len != measured or i in key_to_record or op.locus[0] != expected_readout[i]:
                raise ValueError(f"Unexpected IQM measurement key or wire: {i}")
            key_to_record[i] = len(key_to_record)
            native.append("M", qs)
            order.append(epochs[("measure", i)].popleft())
        elif op.name != "barrier":
            raise ValueError(f"Unexpected IQM gate {op.name}")
    if any(epochs.values()) or len(key_to_record) != measured:
        raise ValueError("CZ or measurement missing")
    basis = {}
    for name, ids, args in checks:
        targets = [stim.target_rec(key_to_record[i] - measured) for i in ids]
        native.append(name, targets, args)
        row = 0
        for i in ids:
            row ^= 1 << i
        while row:
            pivot = row.bit_length()
            if pivot not in basis:
                basis[pivot] = row
                break
            row ^= basis[pivot]
    # Stim rejects any detector or observable that is random on ideal execution.
    native.detector_error_model()
    rank = len(basis)
    if native.count_determined_measurements() != rank or source.count_determined_measurements() != rank:
        raise ValueError("Ideal measurement constraints differ in rank")
    perm = [key_to_record[i] for i in range(measured)]
    rec = native.reference_sample()[perm].reshape(1,-1)
    det, obs = source.compile_m2d_converter().convert(measurements=rec, separate_observables=True)
    if det.any() or obs.any():
        raise ValueError("Ideal measurement parity signs differ")
    return dict(measurements=measured, independent_parities=rank, ideal_distribution_matches=True,
                cz_or_measures_listed_after_a_later_layer=int(np.sum(np.array(order)<np.maximum.accumulate(order))),
                native_operations=dict(Counter(op.name for op in instructions)), swaps=0)


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main(submit):
    if submit:
        backend = connect()
    else:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        backend = IQMFakeAphrodite()
    # Use the same named physical qubits for the comparison with the original run.
    previous_layout = json.loads((PREVIOUS/"layout-r3.json").read_text())["layout"]
    indices = {i: backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
    folder = Path("results/translation_check")/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    print("Output:",folder,flush=True)
    suite = {}
    for rounds in (3,5):
        for protected in (False,True):
            circuit, compiled, meta = prepare(3,rounds,"Z",backend,noise_family="native",
                schedule="alternating",fixed_layout=previous_layout,preserve_ticks=protected)
            if submit:
                req = backend.create_run_request(compiled,shots=4000)
                ops = req.circuits[0].instructions
            else:
                ops = serialize_instructions(compiled,indices)
            check = audit(circuit,ops,[indices[i] for i in previous_layout])
            if protected and (check["cz_or_measures_listed_after_a_later_layer"] or not check["native_operations"].get("barrier")):
                raise ValueError("IQM request did not preserve the marked layers")
            tag = ("barriers" if protected else "original")+f"-r{rounds}"
            save(folder/(tag+"-instructions.json"),[dict(name=o.name,locus=o.locus,args=o.args) for o in ops])
            save(folder/(tag+"-audit.json"),dict(check,layout=previous_layout,depth=meta["depth"],
                live=submit,calibration_set=str(backend.architecture.calibration_set_id)))
            print(tag,check,flush=True)
            if protected:
                model,prior = mapped_decoder_model(circuit,backend,previous_layout,.003,"balanced")
                model.to_file(str(folder/f"decoder-r{rounds}.stim"))
                suite[rounds] = circuit,compiled,model
    if submit:
        for rounds,(circuit,compiled,model) in suite.items():
            job = backend.run(compiled,shots=4000)
            save(folder/f"job-r{rounds}.json",dict(job_id=job.job_id()))
            print("Submitted",rounds,job.job_id(),flush=True)
            result = job.result()
            counts = result.get_counts()
            save(folder/f"counts-r{rounds}.json",dict(counts=counts,job_id=job.job_id(),
                calibration_set=str(result.results[0].calibration_set_id)))
            syn = process_counts(counts,circuit,4000)
            stats = decode_hardware_results(syn,model,"local_likelihood")
            save(folder/f"errors-r{rounds}.json",dict(stats,detector_rates=syn["detector_firing_rate"].tolist()))
            print(rounds,stats,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit",action="store_true",help="Run the two circuits with barriers on Emerald.")
    main(parser.parse_args().submit)

