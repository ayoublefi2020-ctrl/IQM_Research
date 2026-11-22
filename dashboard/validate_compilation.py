import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
from run_on_hardware import prepare
from native_memory import make_native_memory
from twirl_memory import compile_qrisp,pmpt,audit
from iqm.qiskit_iqm.qiskit_to_iqm import serialize_instructions
backend=IQMFakeAphrodite()
results=[]
for basis in "ZX":
    for rounds in (3,20):
        clean,qc,meta=prepare(5,rounds,basis,backend,noise_family="native",schedule="alternating",preserve_ticks=True)
        names={i:backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
        wire_names=[names[i] for i in meta["layout"]]
        for pipeline in ("qiskit","qrisp"):
            ops=(list(serialize_instructions(qc,names)) if pipeline=="qiskit" else compile_qrisp(clean,backend,wire_names))
            base=audit(clean,ops,wire_names)
            assert base["ideal_distribution_matches"] and base["swaps"]==0
            assert base["native_operations"]["cz"]==80*rounds
            for seed in (22112026,22112027):
                assert audit(clean,pmpt(ops,seed),wire_names)==base
            results.append(dict(basis=basis,rounds=rounds,pipeline=pipeline,source="COMPILATION_ONLY",audit=base,twirl_seeds=[22112026,22112027]))
            print(basis,rounds,pipeline,"verified",flush=True)
Path("research_data/distance_5/fixture_compilation.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
