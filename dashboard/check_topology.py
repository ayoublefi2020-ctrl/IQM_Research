import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import networkx as nx
from native_memory import make_native_memory
from run_on_hardware import connect, prepare
from stim_to_qiskit import stim_to_qiskit

def inspect(backend, source):
    dest=Path("research_data/hardware_characterization")
    dest.mkdir(parents=True,exist_ok=True)
    names=[backend.index_to_qubit_name(i) for i in range(backend.num_qubits)]
    couplings=[list(pair) for pair in sorted({tuple(sorted(edge)) for edge in backend.target["cz"] if edge})]
    graph=nx.Graph()
    graph.add_nodes_from(range(len(names)))
    graph.add_edges_from(couplings)
    pos=nx.kamada_kawai_layout(graph)
    positions=[[365+300*float(pos[i][0]),195+170*float(pos[i][1])] for i in graph]
    result=dict(source=source,calibration=str(backend.architecture.calibration_set_id),qubits=names,
                edges=couplings,positions=positions,distances={})
    for d in (3,5):
        clean=make_native_memory(d,3,"Z","alternating")
        qc,_,_=stim_to_qiskit(clean)
        logical=nx.Graph()
        logical.add_nodes_from(range(qc.num_qubits))
        logical.add_edges_from(tuple(qc.find_bit(q).index for q in inst.qubits) for inst in qc.data if inst.operation.num_qubits==2)
        emb=next(nx.algorithms.isomorphism.GraphMatcher(graph,logical).subgraph_monomorphisms_iter(),None)
        record=dict(qubits=qc.num_qubits,required_pairs=logical.number_of_edges(),exact_patch=emb is not None)
        if emb:
            reverse={l:p for p,l in emb.items()}
            _,compiled,meta=prepare(d,3,"Z",backend,noise_family="native",schedule="alternating",fixed_layout=[reverse[i] for i in range(qc.num_qubits)],preserve_ticks=True)
            record.update(meta)
        result["distances"][str(d)]=record
        print(d,record,flush=True)
    (dest/"topology.json").write_text(json.dumps(result,indent=2),encoding="utf-8")

if __name__=="__main__":
    if "--live" in sys.argv:
        inspect(connect(use_metrics=False),"IQM live CZ calibration")
    else:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        inspect(IQMFakeAphrodite(),"IQM Aphrodite SDK fixture")
