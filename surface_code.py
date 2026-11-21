"""Rotated surface-code memories with one shared measurement record for Stim and Qiskit."""
import stim

from internal_helpers import get_meas_order, get_qubit_lists

DEFAULT_NOISE = dict(after_clifford_depolarization=0.003, after_reset_flip_probability=0.003,
                     before_measure_flip_probability=0.003, before_round_data_depolarization=0.003)


def make_stim_circuit(distance, rounds, basis="Z", no_reset=True, noise=None):
    """Readout noise flips the reported bit. Preparation noise acts only after real resets."""
    basis = basis.upper()
    if basis not in ("X", "Z") or distance < 2 or rounds < 1:
        raise ValueError("Use X or Z, distance >= 2 and rounds >= 1.")
    params = dict(noise or {})
    readout = params.pop("before_measure_flip_probability", 0)
    prep = params.pop("after_reset_flip_probability", 0)
    if not all(0 <= v <= 1 for v in [readout, prep, *params.values()]):
        raise ValueError("Noise probabilities must be between zero and one.")
    template = stim.Circuit.generated("surface_code:rotated_memory_" + basis.lower(),
                                      distance=distance, rounds=rounds, **params)
    out = stim.Circuit()
    previous = {}
    substitutions = []
    for op in template.flattened():
        name, tg = op.name, op.targets_copy()
        if name in ("M", "MX", "MR"):
            for t in tg:
                j = len(substitutions)
                indices = [j]
                if no_reset and name == "MR" and t.value in previous:
                    indices.append(previous[t.value])
                substitutions.append(indices)
                previous[t.value] = j
            out.append("M" if no_reset and name == "MR" else name, tg, readout)
            if prep and name == "MR" and not no_reset:
                out.append("X_ERROR", tg, prep)
        elif name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            # Replace every reference to a fresh-ancilla syndrome by its raw
            # measurement parity. This also transforms the final data checks.
            parity = set()
            for t in tg:
                parity.symmetric_difference_update(substitutions[len(substitutions) + t.value])
            out.append(name, [stim.target_rec(i - len(substitutions)) for i in sorted(parity)],
                       op.gate_args_copy())
        else:
            out.append(op)
            if prep and name in ("R", "RX"):
                out.append("X_ERROR" if name == "R" else "Z_ERROR", tg, prep)
    return out


def get_circuit_info(circuit):
    data, anc = get_qubit_lists(circuit)
    return dict(num_qubits=len(data)+len(anc), num_data_qubits=len(data), num_anc_qubits=len(anc),
                num_measurements=circuit.num_measurements, num_detectors=circuit.num_detectors,
                num_observables=circuit.num_observables, data_stim_indices=data,
                anc_stim_indices=anc, meas_order=get_meas_order(circuit))


def make_qiskit_circuit(distance, rounds, basis="Z", no_reset=True):
    from stim_to_qiskit import stim_to_qiskit
    return stim_to_qiskit(make_stim_circuit(distance, rounds, basis, no_reset))[0]


def make_qrisp_experiment(distance, rounds, basis="Z", no_reset=True, p=None):
    """Optional original Qrisp prototype, Z basis only; production runner uses Qiskit."""
    if basis.upper() != "Z" or p:
        raise NotImplementedError("Use the Qiskit track for X memory or noisy models.")
    from stim_to_qrisp import stim_to_detector_experiment
    return stim_to_detector_experiment(make_stim_circuit(distance, rounds, basis, no_reset),
                                       no_reset=False)
