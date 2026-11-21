"""Verify native scheduling, IQM measurement keys and decoded readout against known faults."""
import itertools
import json
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import numpy as np
from qiskit_aer import AerSimulator
from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
from iqm.qiskit_iqm.qiskit_to_iqm import serialize_instructions, MeasurementKey

from native_memory import make_native_memory,SCHEDULES
from run_on_hardware import DEFAULT_SELECTION, connect, prepare, process_counts, decode_hardware_results, run
from internal_helpers import get_qubit_lists,get_meas_order
from stim_to_qiskit import stim_to_qiskit
import stim


class OptimizationTests(unittest.TestCase):
    def test_metrics_fallback(self):
        with patch("iqm.qiskit_iqm.IQMProvider") as provider:
            connected=Mock()
            get_backend=provider.return_value.get_backend
            get_backend.side_effect=[RuntimeError("metrics endpoint is unavailable"),connected]
            with self.assertWarns(UserWarning):
                self.assertIs(connect(token="unit-test"),connected)
            self.assertEqual([call.kwargs["use_metrics"] for call in get_backend.call_args_list],[True,False])

    def test_hardware_result_pipeline_offline(self):
        backend=IQMFakeAphrodite()
        def simulated_job(qc,shots):
            job=Mock()
            job.job_id.return_value=f"offline-{qc.num_clbits}"
            result=job.result.return_value
            result.results=[Namespace(calibration_set_id="test-calibration")]
            result.get_counts.return_value={"0"*qc.num_clbits:shots}
            return job
        with TemporaryDirectory() as output:
            args=Namespace(selection=str(DEFAULT_SELECTION),decoder=None,noise_model=None,profile=None,
                           schedule=None,p=None,distance=3,basis="Z",decoder_weights=None,iqm_fake=False,
                           live_compile=False,submit=True,simulate=False,device="emerald",no_metrics=False,
                           rounds=[2,3],shots=100,output=output,layout_candidates=64)
            with patch("run_on_hardware.connect",return_value=backend), patch.object(backend,"run",side_effect=simulated_job), redirect_stdout(StringIO()):
                run(args)
            folder,=Path(output).iterdir()
            for rounds in args.rounds:
                counts=json.loads((folder/f"counts-r{rounds}.json").read_text())
                self.assertEqual(counts["calibration_set"],"test-calibration")
                self.assertEqual(sum(counts["counts"].values()),100)
                errors=json.loads((folder/f"errors-r{rounds}.json").read_text())
                self.assertEqual(errors["failures"],0)
                self.assertTrue((folder/f"decoder-r{rounds}.stim").is_file())
            self.assertTrue((folder/"fit.json").is_file())

    def test_two_fault_decoder_against_explicit_enumeration(self):
        from likelihood_decoder import FaultLikelihoodDecoder
        dem=stim.DetectorErrorModel("""
            error(0.10) D0
            error(0.12) D1 L0
            error(0.01) D0 D1
            error(0.04) D0 L0
        """)
        class TestModel:
            num_detectors=2
            num_observables=1
            def detector_error_model(self, **options):
                return dem
        dec=FaultLikelihoodDecoder(TestModel())
        mechanisms=[(1,0,.10),(2,1,.12),(3,0,.01),(1,1,.04)]
        mass=np.zeros((4,2))
        for size in (0,1,2):
            for combo in itertools.combinations(mechanisms,size):
                syndrome=logical=0
                odds=1.
                for mask,flip,p in combo:
                    syndrome ^= mask
                    logical ^= flip
                    odds *= p/(1-p)
                mass[syndrome,logical]+=odds
        det=np.array([[(v&1)!=0,(v&2)!=0] for v in range(4)])
        np.testing.assert_array_equal(dec.decode_batch(det)[:,0],mass.argmax(axis=1))

    def test_schedule_detectors_and_distance(self):
        for d,b,s,r in itertools.product((3,5,7),"ZX",SCHEDULES,(1,2,5)):
            with self.subTest(d=d,b=b,s=s,r=r):
                c=make_native_memory(d,r,b,s,.003)
                clean=c.without_noise()
                self.assertEqual(clean.count_determined_measurements(),c.num_detectors+1)
                self.assertEqual(c.num_detectors,(d*d-1)*r)
                self.assertEqual(len(c.shortest_graphlike_error()),d)
                raw=clean.compile_sampler(seed=789).sample(64)
                det,obs=clean.compile_m2d_converter().convert(measurements=raw,separate_observables=True)
                self.assertFalse(det.any() or obs.any())

    def test_corrects_one_readout_fault_but_not_a_logical_string(self):
        for b,r in itertools.product("XZ",(2,8)):
            c=make_native_memory(3,r,b,"alternating")
            model=make_native_memory(3,r,b,"alternating",.003)
            data,_=get_qubit_lists(c)
            for flip in ([data[0]],data):
                faulty=stim.Circuit()
                for op in c:
                    if op.name=="M":
                        for t in op.targets_copy():
                            faulty.append("M",[t],float(t.value in flip))
                    else:
                        faulty.append(op)
                raw=faulty.compile_sampler(seed=99).sample(128)
                det,obs=c.compile_m2d_converter().convert(measurements=raw,separate_observables=True)
                stats=decode_hardware_results(dict(det_events=det,obs_flips=obs),model,"local_likelihood")
                self.assertEqual(stats["failures"],0 if len(flip)==1 else 128)

    def test_noiseless_compiled_and_iqm_keys(self):
        backend=IQMFakeAphrodite()
        for b in "XZ":
            c,local,_=prepare(3,3,b,noise_family="native",schedule="alternating")
            counts=AerSimulator(method="stabilizer").run(local,shots=128,seed_simulator=901).result().get_counts()
            syn=process_counts(counts,c,128)
            self.assertFalse(syn["det_events"].any() or syn["obs_flips"].any())
            _,native,meta=prepare(3,3,b,backend,noise_family="native",schedule="alternating")
            names={i:backend.index_to_qubit_name(i) for i in range(backend.num_qubits)}
            ops=serialize_instructions(native,names)
            measured={}
            for op in ops:
                if op.name=="measure":
                    key=MeasurementKey.from_string(op.args["key"])
                    self.assertNotIn(key.clbit_idx,measured)
                    measured[key.clbit_idx]=op.locus[0]
            _,dense,_=stim_to_qiskit(c)
            expected=[names[meta["layout"][dense[q]]] for q in get_meas_order(c)]
            self.assertEqual([measured[i] for i in range(len(measured))],expected)
            self.assertEqual(meta["operations"]["cz"],72)


if __name__=="__main__":
    unittest.main()
