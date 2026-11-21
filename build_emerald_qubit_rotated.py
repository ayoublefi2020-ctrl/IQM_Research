"""Place the rotated patch on the example Emerald grid or an actual target's CZ graph."""
from collections import Counter
from itertools import islice
from math import isfinite, log1p

import rustworkx as rx


def build_emerald_qubit_map(stim_circuit, grid_top_left=41, grid_n_rows=5, grid_n_cols=5,
                           row_stride=-8, col_stride=1, qiskit_offset=-1):
    coords = sorted(stim_circuit.get_final_qubit_coordinates().items())
    rotated = [(int((y-x)/2), int((y+x)/2)) for _,(x,y) in coords]
    top, left = map(min, zip(*rotated))
    physical = {}
    for i,(r,c) in enumerate(rotated):
        r, c = r-top, c-left
        if r >= grid_n_rows or c >= grid_n_cols:
            raise ValueError("Code does not fit this example patch. Use the live target layout.")
        physical[i] = grid_top_left + qiskit_offset + r*row_stride + c*col_stride
    if len(set(physical.values())) != len(physical):
        raise ValueError("Grid strides assign multiple qubits to a single site.")
    return physical


def print_qubit_map(stim_circuit, *args, **kwargs):
    for dense, physical in build_emerald_qubit_map(stim_circuit,*args,**kwargs).items():
        print(f"Dense {dense:2} -> physical {physical:2}")


def _candidate_layouts(qc, physical_edges, n_physical, limit):
    """Enumerate a bounded set of native embeddings in reproducible VF2 order."""
    if limit < 1:
        raise ValueError("layout candidate limit must be positive")
    def graph(n, edges):
        g = rx.PyGraph(multigraph=False)
        g.add_nodes_from(range(n))
        g.add_edges_from_no_data(sorted({tuple(sorted(e)) for e in edges}))
        return g
    interactions = {tuple(qc.find_bit(q).index for q in inst.qubits)
                    for inst in qc.data if inst.operation.num_qubits == 2}
    mappings = rx.vf2_mapping(graph(n_physical, physical_edges), graph(qc.num_qubits, interactions),
                              subgraph=True, induced=False, id_order=False, call_limit=2000000)
    for placement in islice(mappings, limit):
        by_dense = {dense: physical for physical, dense in placement.items()}
        yield [by_dense[i] for i in range(qc.num_qubits)]


def exact_layout(qc, physical_edges, n_physical):
    first = next(_candidate_layouts(qc, physical_edges, n_physical, 1), None)
    if first is None:
        raise ValueError("No exact placement found within search budget; try a smaller distance.")
    return first


def calibration_errors(backend):
    """Return CZ and readout error proxies, indexed by physical qubit number."""
    def values(op):
        out = {}
        for locus, props in backend.target[op].items():
            e = getattr(props, "error", None)
            if locus and e is not None and isfinite(e) and 0 <= e < 1:
                key = tuple(sorted(locus))
                # IQM's CZ is symmetric. Use the conservative value if a target
                # reports both directions with different properties.
                out[key] = max(e, out.get(key, 0.))
        return out
    edges, readout = values("cz"), values("measure")
    source = "backend InstructionProperties"
    # IQM fake devices store error parameters separately from the target.
    if not edges and not readout and hasattr(backend, "error_profile"):
        profile = backend.error_profile
        idx = backend.qubit_name_to_index
        # Average gate infidelity for a two-qubit depolarizing channel = 3 lambda / 4.
        edges = {tuple(sorted((idx(a), idx(b)))): 0.75 * lam
                 for (a,b),lam in profile.two_qubit_gate_depolarizing_error_parameters["cz"].items()}
        readout = {(idx(q),): (err["0"] + err["1"]) / 2 for q,err in profile.readout_errors.items()}
        source = "IQM synthetic error profile (CZ depolarization and mean assignment error)"
    return edges, readout, source if edges or readout else "no error data"


def calibrated_layout(qc, backend, limit=1024):
    """Minimize frequency-weighted CZ/readout negative log fidelity over exact layouts."""
    edge_err, ro_err, source = calibration_errors(backend)
    measurable = {q[0] for q in backend.target["measure"] if q and len(q)==1}
    edges = [pair for pair in backend.target["cz"] if pair and all(q in measurable for q in pair)]
    cz_count = Counter()
    ro_count = Counter()
    for inst in qc.data:
        qubits = tuple(qc.find_bit(q).index for q in inst.qubits)
        if inst.operation.name == "measure":
            ro_count[qubits] += 1
        elif inst.operation.name in ("cx", "cz"):
            cz_count[tuple(sorted(qubits))] += 1
    def component(count, errors, layout):
        if not errors:
            return 0., sum(count.values())
        worst = max(errors.values())
        score, missing = 0., 0
        for logical, multiplicity in count.items():
            physical = tuple(sorted(layout[i] for i in logical))
            if physical not in errors:
                missing += multiplicity
            score -= multiplicity * log1p(-errors.get(physical, worst))
        return score, missing
    def describe(layout):
        two, miss_two = component(cz_count, edge_err, layout)
        ro, miss_ro = component(ro_count, ro_err, layout)
        return dict(layout=layout, score=two+ro, cz_score=two, readout_score=ro,
                    missing_cz_locations=miss_two, missing_readout_locations=miss_ro)
    layouts = _candidate_layouts(qc, edges, backend.num_qubits, limit if edge_err or ro_err else 1)
    baseline = next(layouts, None)
    if baseline is None:
        raise ValueError("No measurable exact CZ embedding found within VF2's search budget.")
    best = first = describe(baseline)
    total = 1
    for layout in layouts:
        candidate = describe(layout)
        total += 1
        if candidate["score"] < best["score"]:
            best = candidate
    return best["layout"], dict(metric_source=source, candidates_evaluated=total,
                                candidate_limit=limit, score_units="negative log fidelity proxy",
                                missing_policy="worst reported value within each operation; omit absent families",
                                first_exact=first, selected=best)
