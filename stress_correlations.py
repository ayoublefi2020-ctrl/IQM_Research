"""Blind calibration of a repeated local two-data-qubit fault on a no-reset memory.

Two possible extra channels have identical one-qubit Pauli marginals. Fit each
candidate's detector parity moments using calibration shots, then decode an
independent set of shots with ordinary matching. See PAPER_STUDY.md for scope.
"""
import argparse
import csv
import itertools
import json
from pathlib import Path

import numpy as np
import stim
from scipy.stats import binomtest

from qec_analysis import failures, matcher, noise_model
from surface_code import make_stim_circuit


def add_faults(circuit, rounds, kind, q):
    """Add XX and ZZ mechanisms to each of two data bonds before each round."""
    if kind not in ("independent", "joint", "nominal") or not 0 <= q < .5:
        raise ValueError("Invalid fault kind or probability")
    if not q or kind == "nominal":
        return circuit
    by_xy = {tuple(xy): i for i, xy in circuit.get_final_qubit_coordinates().items()}
    data = {i for (x, y), i in by_xy.items() if x % 2 and y % 2}
    bonds = [(by_xy[1, 1], by_xy[3, 1]), (by_xy[1, 1], by_xy[1, 3])]
    injections = 0
    out = stim.Circuit()
    for op in circuit.flattened():
        out.append(op)
        if op.name != "DEPOLARIZE1" or {t.value for t in op.targets_copy()} != data:
            continue
        injections += 1
        for a, b in bonds:
            for pauli, target in (("X", stim.target_x), ("Z", stim.target_z)):
                if kind == "joint":
                    out.append("CORRELATED_ERROR", [target(a), target(b)], q)
                else:
                    out.append(pauli + "_ERROR", [a, b], q)
    if injections != rounds:
        raise ValueError("Expected exactly one data-idle noise operation per round")
    return out


def features(circuit, rounds):
    """Choose local detector singles and pairs using geometry only."""
    detectors = circuit.get_detector_coordinates()
    probes = sorted(i for i, (x, y, t) in detectors.items()
                    if x <= 4 and y <= 4 and int(t) in {0, 1, rounds//2, rounds})
    return [(i,) for i in probes] + list(itertools.combinations(probes, 2))


def expected_parities(circuit, terms):
    """For independent DEM mechanisms the parity sign means multiply exactly."""
    log_sign = np.zeros(circuit.num_detectors)
    pair_overlap = {}
    for op in circuit.detector_error_model().flattened():
        if op.type != "error":
            continue
        detectors = sorted(t.val for t in op.targets_copy() if t.is_relative_detector_id())
        log_factor = np.log1p(-2 * op.args_copy()[0])
        log_sign[detectors] += log_factor
        for pair in itertools.combinations(detectors, 2):
            pair_overlap[pair] = pair_overlap.get(pair, 0.) + log_factor
    log_moments = [log_sign[term[0]] if len(term) == 1 else
                   log_sign[term[0]] + log_sign[term[1]] - 2 * pair_overlap.get(term, 0.)
                   for term in terms]
    return -.5 * np.expm1(log_moments)


def empirical_parities(dets, terms):
    return np.asarray([dets[:, t[0]].mean() if len(t) == 1 else
                       np.mean(dets[:, t[0]] ^ dets[:, t[1]]) for t in terms])


def analyze(args):
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    records = []
    hypotheses = [("nominal", 0.)] + list(itertools.product(
        ("independent", "joint"), args.q_grid))
    truths = [("nominal", 0.)] + list(itertools.product(("independent", "joint"), args.q))
    for d, basis, p, rounds in itertools.product(args.distance, args.basis, args.p, args.rounds):
        clean = make_stim_circuit(d, rounds, basis, noise=noise_model(p, "uniform"))
        terms = features(clean, rounds)
        models = [add_faults(clean, rounds, kind, q) for kind, q in hypotheses]
        expected = np.asarray([expected_parities(c, terms) for c in models])
        # Prefer detector parities sensitive to the choice of channel at high q.
        # The ordering uses only the candidate models; freeze it before sampling.
        scale = np.sqrt(np.maximum(.001, expected[0]*(1-expected[0])))
        effect = np.ptp(expected, axis=0)/scale
        idx = np.argsort(-effect, kind="stable")[:96]
        selected_terms = [terms[i] for i in idx]
        cached = {}
        for true_kind, true_q in truths:
            actual = add_faults(clean, rounds, true_kind, true_q)
            seeds = rng.integers(0, 2**63, size=2, dtype=np.int64)
            calibration = actual.compile_detector_sampler(seed=int(seeds[0])).sample(args.calibration)
            measured = empirical_parities(calibration, selected_terms)
            score = np.mean(((expected[:, idx]-measured)/scale[idx])**2, axis=1)
            ind = min((i for i,(k,_) in enumerate(hypotheses) if k!="joint"),key=score.__getitem__)
            joint = int(np.argmin(score))
            test, obs = actual.compile_detector_sampler(seed=int(seeds[1])).sample(
                args.shots, separate_observables=True)
            calls = {}
            for i in {0, ind, joint}:
                if i not in cached:
                    cached[i] = matcher(models[i], "plain")
                calls[i] = failures(cached[i], "plain", test, obs)
            a, b = calls[ind], calls[joint]
            records.append(dict(distance=d, basis=basis, p=p, rounds=rounds, truth=true_kind,
                                q=true_q, calibration_seed=int(seeds[0]), validation_seed=int(seeds[1]),
                                calibration_shots=args.calibration, shots=args.shots,
                                independent_q=hypotheses[ind][1], selected=hypotheses[joint][0],
                                selected_q=hypotheses[joint][1], n_features=len(idx),
                                nominal_errors=int(calls[0].sum()), independent_errors=int(a.sum()),
                                selected_errors=int(b.sum()), independent_only=int((a & ~b).sum()),
                                selected_only=int((b & ~a).sum())))
    with (folder/"conditions.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    totals = {}
    for truth in ("all", "nominal", "independent", "joint"):
        rows = [r for r in records if truth == "all" or r["truth"] == truth]
        stats = {k:sum(r[k] for r in rows) for k in ("calibration_shots", "shots", "nominal_errors",
                 "independent_errors", "selected_errors", "independent_only", "selected_only")}
        n = stats["independent_only"] + stats["selected_only"]
        stats["paired_test_p"] = binomtest(stats["independent_only"], n).pvalue if n else 1.
        stats["family_recovered"] = sum(r["selected"] == r["truth"] for r in rows)
        stats["conditions"] = len(rows)
        totals[truth] = stats
    (folder/"summary.json").write_text(json.dumps({"args":vars(args),"totals":totals}, indent=2))
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--distance", nargs="+", type=int, default=[3, 5])
    ap.add_argument("--basis", nargs="+", choices=["X","Z"], default=["X","Z"])
    ap.add_argument("--p", nargs="+", type=float, default=[.001,.005])
    ap.add_argument("--rounds", nargs="+", type=int, default=[3,12,25])
    ap.add_argument("--q", nargs="+", type=float, default=[.002,.008])
    ap.add_argument("--q-grid", nargs="+", type=float, default=[.001,.003,.006,.01])
    ap.add_argument("--calibration", type=int, default=10000)
    ap.add_argument("--shots", type=int, default=16000)
    ap.add_argument("--seed", type=int, default=31415926)
    ap.add_argument("--output", default="results/correlated_stress")
    args = ap.parse_args()
    if min(args.p) <= 0 or min(args.shots,args.calibration) < 1 or min(args.rounds) < 2:
        ap.error("Use positive noise and shots and at least two rounds.")
    analyze(args)
