import unittest
from import_data import build, register_execution, validate_counts
from server import geometry, inspect_shot, simulate

class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=build()

    def test_normalization(self):
        records=self.db["records"]
        self.assertEqual(len(records),len({row["id"] for row in records}))
        for row in records:
            validate_counts(row["shots"],row["failures"])
            self.assertAlmostEqual(row["probability"],row["failures"]/row["shots"])
            self.assertTrue(row["source"]!="IQM_HARDWARE" or row["job"])

    def test_invalid_counts_and_duplicate_partition(self):
        for shots,failures in ((100,101),(0,0),(None,5),(100,-1),(True,1)):
            with self.assertRaises(ValueError):
                validate_counts(shots,failures)
        seen={}
        register_execution(seen,("job",3,"control"),4000)
        with self.assertRaises(ValueError):
            register_execution(seen,("job",3,"control"),4000)

    def test_shot_resolution(self):
        row=next(r for r in self.db["records"] if r["raw"] and r.get("blocks"))
        result=inspect_shot(row,0)
        self.assertEqual(sum(result["weights"]),row["shots"])
        self.assertLessEqual(len(result["events"]),len(result["coordinates"]))
        with self.assertRaises(ValueError):
            inspect_shot(row,row["shots"])
        with self.assertRaises(ValueError):
            inspect_shot(dict(row,raw=None),0)

    def test_geometry(self):
        for d,nodes,edges in ((3,17,24),(5,49,80)):
            shape=geometry(d)
            self.assertEqual(len(shape["nodes"]),nodes)
            self.assertEqual(len(shape["edges"]),edges)
            self.assertEqual(set(shape["layers"].values()),{0,1,2,3})

    def test_basis_pilot_raw_replay(self):
        import numpy as np
        import stim
        from archive import ROOT
        from import_data import read
        from qec_analysis import matcher, failures
        from verify_routed_payload import verify_payload
        from native_memory import make_native_memory
        rows=[r for r in self.db["records"] if "/basis_pilot/" in r["file"]]
        self.assertEqual({r["basis"] for r in rows},{"X","Z"})
        self.assertEqual(len({(r["job"],r["calibration"]) for r in rows}),1)
        for row in rows:
            basis=row["basis"]
            model=stim.Circuit.from_file(str(ROOT/row["model"]))
            folder=(ROOT/row["raw"]).parent
            verify_payload(make_native_memory(3,3,basis,"alternating"),read(folder/f"{basis}-instructions.json"))
            with np.load(ROOT/row["raw"],allow_pickle=False) as data:
                det,obs=model.compile_m2d_converter().convert(measurements=data["records"],separate_observables=True)
            self.assertEqual(int(failures(matcher(model,"correlated"),"correlated",det,obs).sum()),row["failures"])

    def test_routing_audits_use_existing_shots(self):
        rows=[r for r in self.db["records"] if r.get("routed_redecode")]
        self.assertEqual(len(rows),2)
        for row in rows:
            alt=row["routed_redecode"]
            self.assertEqual(alt["shots"],row["shots"])
            self.assertEqual(alt["failures"],row["failures"]-alt["corrected"]+alt["newly_failed"])

if __name__=="__main__":
    unittest.main()
