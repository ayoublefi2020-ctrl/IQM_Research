"""Reanalyse archived pilot shots and isolate routing cost under an assumed CZ channel."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import stim
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_memory import make_native_memory
from qec_analysis import failures, matcher, wilson
from verify_routed_payload import verify_payload, routed_model


def stats(flags):
    count = int(flags.sum())
    return dict(failures=count, shots=len(flags), interval=wilson(count, len(flags)))


def direct_parities(clean, raw):
    """Evaluate the no-reset circuit's published rec[] supports directly on IQM columns."""
    n = 0
    checks = []
    observable = np.zeros(len(raw), dtype=bool)
    for op in clean:
        targets = op.targets_copy()
        if op.name == "M":
            n += len(targets)
        elif op.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            bits = raw[:, [n+t.value for t in targets]].sum(axis=1) % 2
            if op.name == "DETECTOR":
                checks.append(bits)
            else:
                observable ^= bits.astype(bool)
    assert n == raw.shape[1]
    return np.column_stack(checks), observable


def run(folder="routed_hardware"):
    dest = ROOT / "research_data/distance_5" / folder
    raw_path = dest / "r3-raw.npz"
    with np.load(raw_path, allow_pickle=False) as bundle:
        raw = bundle["records"]
    clean = make_native_memory(5, 3, "Z", "alternating")
    original = stim.Circuit.from_file(str(dest / "decoder-r3.stim"))
    ops = json.loads((dest / "instructions.json").read_text())
    saved = json.loads((dest / "errors-r3.json").read_text())
    result = dict(job=saved["job_id"], raw_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                  ideal_payload=verify_payload(clean, ops))
    det, obs = original.compile_m2d_converter().convert(measurements=raw, separate_observables=True)
    checks, parity = direct_parities(clean, raw)
    assert np.array_equal(checks, det) and np.array_equal(parity, obs[:, 0])
    base = failures(matcher(original, "correlated"), "correlated", det, obs)
    assert base.sum() == saved["failures"] and np.allclose(det.mean(0), saved["detector_rates"])
    result.update(archive_decode=stats(base), detectors=det.shape[1], independent_parity_check=True,
                  raw_observable_flips=int(parity.sum()), mean_hardware_detector_firing=float(det.mean()))
    prior = dict(cz_error=.003, rotation_error=.00075, readout_error=.003)
    model, _, _ = routed_model(clean, ops, **prior)
    alternate = failures(matcher(model, "correlated"), "correlated", det, obs)
    gained = int(np.sum(base & ~alternate))
    lost = int(np.sum(~base & alternate))
    result["routed_redecode"] = dict(stats(alternate), prior=prior, corrected=gained, newly_failed=lost,
            paired_exact_p=binomtest(gained, gained+lost, .5).pvalue if gained+lost else 1.)
    # Hold gate error probabilities, syndrome definitions and decoder method fixed.
    # Only CZs experience errors. The two schedules differ in the number and location of CZs.
    ideal_czs = sum(len(op.targets_copy())//2 for op in clean if op.name == "CZ")
    routed_czs = sum(op["name"] == "cz" for op in ops)
    result["cz_only_simulations"] = []
    for p in (.003, .01):
        logical = stim.Circuit()
        for op in clean:
            logical.append(op)
            if op.name == "CZ":
                logical.append("DEPOLARIZE2", op.targets_copy(), p)
        physical, _, _ = routed_model(clean, ops, cz_error=p)
        for label, circuit, ncz in (("direct", logical, ideal_czs), ("routed", physical, routed_czs)):
            events, flips = circuit.compile_detector_sampler(seed=221126).sample(20000, separate_observables=True)
            flags = failures(matcher(circuit, "correlated"), "correlated", events, flips)
            result["cz_only_simulations"].append(dict(stats(flags), circuit=label, cz=ncz, p_cz=p,
                    seed=221126, mean_detector_firing=float(events.mean())))
    out = dest.parent / ("pilot_audit.json" if folder=="routed_hardware" else "followup_audit.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    for folder in ("routed_hardware", "routing_followup"):
        if (ROOT / "research_data/distance_5" / folder / "errors-r3.json").exists():
            print(json.dumps(run(folder), indent=2))
