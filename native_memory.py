"""No-reset memories compiled into CZ and local basis rotations before adding noise."""
import stim

from internal_helpers import get_qubit_lists
from surface_code import make_stim_circuit

# Error per H, CZ, initial preparation, reported bit, and data idle during readout.
# Rates are illustrative multiples of p. A physical H is modeled as one noisy rotation.
PROFILES = {"balanced": (.25, 1, 1, 1, 1), "readout": (.25, 1, 1, 4, 1),
            "idle": (.25, 1, 1, 1, 4), "phase": (.25, 1, 1, 1, 4)}
SCHEDULES = ("literal", "forward", "alternating")


def make_native_memory(distance, rounds, basis="Z", schedule="forward", p=0., profile="balanced"):
    """literal expands each CX independently; other schedules cancel adjacent H on each wire."""
    if schedule not in SCHEDULES or profile not in PROFILES:
        raise ValueError("Unknown schedule or noise profile")
    h_err, cz_err, prep, ro, idle = (p*n for n in PROFILES[profile])
    if not 0 <= p <= 1/max(PROFILES[profile]):
        raise ValueError("Noise parameter outside probability range")
    template = make_stim_circuit(distance, rounds, basis)
    ops = list(template)
    data, ancillas = get_qubit_lists(template)
    layer_indices = [i for i,op in enumerate(ops) if op.name=="CX"]
    if len(layer_indices) != 4*rounds:
        raise ValueError("Expected four CX layers per round")
    if schedule == "alternating":
        for j in range(4,len(layer_indices),8):
            group = layer_indices[j:j+4]
            layers = [ops[i] for i in reversed(group)]
            for i,op in zip(group,layers):
                ops[i] = op
    circuit = stim.Circuit()
    pending = set()

    def flush(qubits):
        active = sorted(pending.intersection(qubits))
        if active:
            circuit.append("H",active)
            if h_err:
                circuit.append("DEPOLARIZE1",active,h_err)
            pending.difference_update(active)

    def toggle(qubits):
        pending.symmetric_difference_update(qubits)
        if schedule=="literal":
            flush(qubits)

    for op in ops:
        name = op.name
        if name in ("QUBIT_COORDS","DETECTOR","OBSERVABLE_INCLUDE","TICK"):
            circuit.append(op)
            continue
        qs = [t.value for t in op.targets_copy()]
        if name in ("RX","R"):
            circuit.append("R",qs)
            if prep:
                circuit.append("X_ERROR",qs,prep)
            if name=="RX":
                toggle(qs)
        elif name=="H":
            toggle(qs)
        elif name=="CX":
            targets=qs[1::2]
            toggle(targets)
            flush(qs)
            circuit.append("CZ",qs)
            if cz_err:
                circuit.append("DEPOLARIZE2",qs,cz_err)
            toggle(targets)
        elif name in ("M","MX"):
            if name=="MX":
                toggle(qs)
            flush(qs)
            if idle and set(qs).intersection(ancillas):
                circuit.append("Z_ERROR" if profile=="phase" else "DEPOLARIZE1",data,idle)
            circuit.append("M",qs,ro)
        else:
            raise ValueError(f"Unsupported surface-code instruction {name}")
    if pending:
        raise ValueError("Unresolved final measurement basis")
    return circuit
