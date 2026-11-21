"""Compare the two distance-3 Z circuits in the same Emerald batch. No submission without --submit."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import stim

from internal_helpers import counts_to_measurement_array, get_qubit_lists
from investigate_translation import audit
from likelihood_decoder import FaultLikelihoodDecoder
from native_memory import make_native_memory
from qec_analysis import fit_rate
from run_on_hardware import connect, prepare


def our_si1000(clean, noise):
    """Apply the colleague's SI1000 convention, including persistent pre-readout flips."""
    out = stim.Circuit()
    data, ancillas = get_qubit_lists(clean)
    for op in clean:
        qs = [t.value for t in op.targets_copy()]
        if op.name == "M":
            # Stim can merge adjacent banks, so split them at the ancilla/data boundary.
            for bank in (ancillas, data):
                targets = [q for q in qs if q in bank]
                if targets:
                    out.append("X_ERROR", targets, noise.p_meas)
                    out.append("M", targets)
                    if bank is ancillas:
                        out.append("DEPOLARIZE1", data, noise.p_idle_meas)
        else:
            out.append(op)
            if op.name == "R":
                out.append("X_ERROR", qs, noise.p_reset)
            elif op.name == "H":
                out.append("DEPOLARIZE1", qs, noise.p1)
            elif op.name == "CZ":
                out.append("DEPOLARIZE2", qs, noise.p2)
    return out


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def score(folder):
    from qec.decode import decode

    rows = []
    for label, rounds in ORDER:
        tag = f"{label}-r{rounds}"
        model = stim.Circuit.from_file(str(folder/(tag+".stim")))
        counts = json.loads((folder/(tag+"-counts.json")).read_text())
        raw = counts_to_measurement_array(counts, model.num_measurements, 4000)
        det, obs = model.compile_m2d_converter().convert(measurements=raw, separate_observables=True)
        row = dict(project=label, rounds=rounds, shots=len(raw), raw=int(obs.sum()))
        for name in ("correlated","bposd"):
            row[name] = int(decode(det,obs,model,name).errors)
        pred = FaultLikelihoodDecoder(model,split_temporally=True).decode_batch(det)
        row["local_likelihood"] = int(np.count_nonzero(pred != obs))
        rows.append(row)
        print(row, flush=True)
    fits = {}
    for label in ("ours","colleague"):
        pts = sorted([row for row in rows if row["project"]==label],key=lambda row:row["rounds"])
        fits[label] = {d:fit_rate([3,5],[row[d] for row in pts],[4000,4000])
                       for d in ("bposd","correlated","local_likelihood")}
    save(folder/"scores.json",dict(rows=rows,fits=fits))


ORDER = (("ours",3),("colleague",3),("colleague",5),("ours",5))


def project_decoders(folder, peer):
    """Re-score the saved hardware shots with each project's own decoder and prior."""
    from device_noise import mapped_decoder_model
    from qec import NoiseModel, build_memory_circuit
    from qec.decode import decode
    settings = json.loads((folder/"settings.json").read_text())
    names = json.loads((peer/"results/hw/pending_20261121-151940_emerald_Z.json").read_text())["physical"]
    char = json.loads((peer/"results/hw/meas_20261121-170050_emerald.json").read_text())
    noise = NoiseModel.si1000(.01).with_characterization(char,{int(i):n for i,n in names.items()})
    backend = None
    stats = {}
    for label, rounds in ORDER:
        tag = f"{label}-r{rounds}"
        path = folder/(tag+"-project-prior.stim")
        if path.exists():
            model = stim.Circuit.from_file(str(path))
        elif label == "ours":
            backend = backend or connect()
            if str(backend.architecture.calibration_set_id) != settings["calibration"]:
                raise ValueError("Live calibration differs from the execution")
            clean = make_native_memory(3,rounds,"Z","alternating")
            model,_ = mapped_decoder_model(clean,backend,settings["physical_layouts"]["ours"],.003,"balanced")
        else:
            model = build_memory_circuit(3,rounds,"Z",True,noise)
        model.to_file(str(path))
        counts = json.loads((folder/(tag+"-counts.json")).read_text())
        raw = counts_to_measurement_array(counts,model.num_measurements,4000)
        det,obs = model.compile_m2d_converter().convert(measurements=raw,separate_observables=True)
        if label == "ours":
            pred = FaultLikelihoodDecoder(model,split_temporally=True).decode_batch(det)
            errors = int(np.count_nonzero(pred != obs))
        else:
            errors = int(decode(det,obs,model,"bposd").errors)
        stats[tag] = dict(errors=errors,shots=len(raw),probability=errors/len(raw))
    save(folder/"project-decoders.json",stats)
    print(stats)


def run(args):
    from qec import build_memory_circuit, NoiseModel, RotatedSurfaceCode
    from qec.hardware import dd_options, stim_to_qiskit, transpile_pinned
    from iqm.qiskit_iqm.qiskit_to_iqm import serialize_instructions

    if args.score:
        score(args.score)
        return
    if args.project_decoders:
        project_decoders(args.project_decoders,args.peer)
        return
    if args.submit:
        backend = connect()
    else:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        backend = IQMFakeAphrodite()
    history = json.loads((args.peer/"results/hw/pending_20261121-151940_emerald_Z.json").read_text())
    graph = RotatedSurfaceCode(3)
    peer_layout = {int(q):backend.qubit_name_to_index(name) for q,name in history["physical"].items()}
    by_xy = {xy:peer_layout[q] for q,xy in graph.coords.items()}
    our_coords = make_native_memory(3,3).get_final_qubit_coordinates()
    # Reflect x to align X/Z boundary checks and preserve the final logical Z row.
    our_layout = [by_xy[6-our_coords[q][0],our_coords[q][1]] for q in sorted(our_coords)]
    noise = NoiseModel.si1000(.01)
    folder = Path("results/project_comparison")/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    circuits, audits = [], {}
    names = {i:backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
    for label, rounds in ORDER:
        tag = f"{label}-r{rounds}"
        if label == "ours":
            clean,compiled,_ = prepare(3,rounds,"Z",backend,noise_family="native",schedule="alternating",
                                       fixed_layout=our_layout,preserve_ticks=True)
            model = our_si1000(clean,noise)
            layout = our_layout
        else:
            clean = build_memory_circuit(3,rounds,"Z",True,None)
            compiled = transpile_pinned(stim_to_qiskit(clean),backend,peer_layout)
            model = build_memory_circuit(3,rounds,"Z",True,noise)
            layout = [peer_layout[q] for q in sorted(peer_layout)]
        compiled.name = tag
        ops = serialize_instructions(compiled,names)
        audits[tag] = audit(clean,ops,[names[i] for i in layout])
        if audits[tag]["native_operations"]["cz"] != 24*rounds:
            raise ValueError("Unexpected CZ count")
        model.to_file(str(folder/(tag+".stim")))
        circuits.append(compiled)
    save(folder/"settings.json",dict(distance=3,basis="Z",shots=4000,order=ORDER,dd="standard on",
        priors="SI1000 p=0.01",primary_decoder="bposd",backend=str(backend.name),submit=args.submit,
        physical_layouts=dict(ours=our_layout,colleague=peer_layout),audits=audits,
        calibration=str(backend.architecture.calibration_set_id)))
    print(folder,flush=True)
    if args.submit:
        job = backend.run(circuits,shots=4000,circuit_compilation_options=dd_options(True))
        save(folder/"job.json",dict(id=job.job_id()))
        print(job.job_id(),flush=True)
        result = job.result()
        for i,(label,r) in enumerate(ORDER):
            save(folder/f"{label}-r{r}-counts.json",result.get_counts(i))
        save(folder/"executed-calibrations.json",[str(x.calibration_set_id) for x in result.results])
        score(folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer",type=Path,required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--submit",action="store_true")
    mode.add_argument("--score",type=Path)
    mode.add_argument("--project-decoders",type=Path)
    args = parser.parse_args()
    sys.path.append(str(args.peer.resolve()))
    run(args)

