"""Offline regression checks for no-reset detectors, layout, readout order and decoder."""
import unittest

import numpy as np
import stim
from qiskit_aer import AerSimulator
from qiskit.providers.fake_provider import GenericBackendV2

from qec_analysis import noise_model
from run_on_hardware import prepare, process_counts, decode_hardware_results
from surface_code import make_stim_circuit, get_circuit_info
from stim_to_qiskit import stim_to_qiskit


class MemoryTests(unittest.TestCase):
    def test_noiseless_boundaries_and_distance(self):
        for basis in "XZ":
            for d in (3,5):
                for r in (1,2,5):
                    with self.subTest(basis=basis,d=d,r=r):
                        circuit = make_stim_circuit(d,r,basis)
                        info = get_circuit_info(circuit)
                        self.assertEqual(info["num_qubits"], 2*d*d-1)
                        self.assertEqual(circuit.num_measurements, (d*d-1)*r+d*d)
                        self.assertEqual(circuit.num_detectors,(d*d-1)*r)
                        self.assertEqual(circuit.num_observables,1)
                        self.assertFalse(any(op.name=="MR" for op in circuit))
                        self.assertFalse(circuit.compile_detector_sampler(seed=4).sample(
                            512,append_observables=True).any())
                        model = make_stim_circuit(d,r,basis,noise=noise_model(.003,"uniform"))
                        self.assertEqual(len(model.shortest_graphlike_error()),d)

    def test_compiled_memory(self):
        sim = AerSimulator(method="stabilizer")
        for basis in "XZ":
            c,qc,_ = prepare(3,3,basis)
            counts = sim.run(qc,shots=128,seed_simulator=5).result().get_counts()
            syn = process_counts(counts,c,128)
            self.assertFalse(syn["det_events"].any() or syn["obs_flips"].any())
            self.assertGreater(len(counts),1)  # random stabilizer signs are retained

    def test_live_layout_on_backend_target(self):
        edges = [[r*5+c,s*5+t] for r in range(5) for c in range(5)
                 for s,t in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)) if 0<=s<5 and 0<=t<5]
        backend = GenericBackendV2(25,basis_gates=["rz","sx","x","cz"],coupling_map=edges,seed=8)
        _,_,meta = prepare(3,3,"Z",backend)
        self.assertEqual(meta["unique_required_pairs"],24)
        self.assertEqual(meta["operations"]["cz"],72)

    def test_physical_and_logical_faults(self):
        sim = AerSimulator(method="stabilizer")
        for basis in "ZX":
            clean = make_stim_circuit(3,3,basis)
            model = make_stim_circuit(3,3,basis,noise=noise_model(.003,"uniform"))
            data = get_circuit_info(clean)["data_stim_indices"]
            for qubits,expected_fails in [([data[0]],0),(data,128)]:
                injected = stim.Circuit()
                for op in clean:
                    if op.name in ("M","MX") and op.targets_copy()[0].value in data:
                        if basis=="X":
                            injected.append("H",qubits)
                        injected.append("X",qubits)
                        if basis=="X":
                            injected.append("H",qubits)
                    injected.append(op)
                qc,_,_ = stim_to_qiskit(injected)
                counts = sim.run(qc,shots=128,seed_simulator=33).result().get_counts()
                syn = process_counts(counts,clean,128)
                for decoder in ("plain","correlated"):
                    self.assertEqual(decode_hardware_results(syn,model,decoder)["failures"],expected_fails)


if __name__ == "__main__":
    unittest.main()
