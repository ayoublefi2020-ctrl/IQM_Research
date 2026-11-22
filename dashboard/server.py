import json
from pathlib import Path
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from import_data import build, read
from archive import ARCHIVE
from native_memory import make_native_memory
from surface_code import make_stim_circuit
from qec_analysis import matcher, failures, wilson

DESIGN=ROOT/"dashboard"
DB=DESIGN/"experiments.json"

def archive_database():
    db=read(DB)
    pilot=ROOT/"research_data/distance_5/routed_hardware/errors-r3.json"
    if pilot.exists() and not any(r["distance"]==5 and r["source"]=="IQM_HARDWARE" for r in db["records"]):
        return build()
    return db

def simulate(data):
    distance, rounds, shots, seed=(int(data[key]) for key in ("distance","rounds","shots","seed"))
    basis, decoder=data["basis"],data["decoder"]
    if distance not in (3,5) or not 1<=rounds<=20 or not 1<=shots<=20000 or not 0<=seed<2**64 or basis not in "XZ" or len(basis)!=1 or decoder not in ("plain","correlated"):
        raise ValueError("Invalid simulation settings")
    import stim
    from internal_helpers import get_qubit_lists
    clean=make_native_memory(distance,rounds,basis,"alternating")
    qubits,ancillas=get_qubit_lists(clean)
    p,cz,ro,prep,idle=(float(data[key]) for key in ("p","cz","readout","prep","idle"))
    if not all(0<=v<=.1 for v in (p,cz,ro,prep,idle)):
        raise ValueError("Noise probabilities must be in [0, 0.1]")
    if data["profile"] not in ("balanced","readout","idle","phase"):
        raise ValueError("Unknown noise profile")
    ro *= 3 if data["profile"]=="readout" else 1
    idle *= 3 if data["profile"] in ("idle","phase") else 1
    circuit=stim.Circuit()
    for op in clean:
        args=op.targets_copy()
        if op.name=="M":
            first=[t for t in args if t.value in ancillas]
            last=[t for t in args if t.value not in ancillas]
            if first:
                circuit.append("M",first,ro)
                circuit.append("Z_ERROR" if data["profile"]=="phase" else "DEPOLARIZE1",qubits,idle)
            if last:
                circuit.append("M",last,ro)
        else:
            circuit.append(op)
            if op.name in ("R","H","CZ"):
                name,prob={"R":("X_ERROR",prep),"H":("DEPOLARIZE1",p),"CZ":("DEPOLARIZE2",cz)}[op.name]
                if prob:
                    circuit.append(name,args,prob)
    det,obs=circuit.compile_detector_sampler(seed=seed).sample(shots,separate_observables=True)
    failed=int(failures(matcher(circuit,decoder),decoder,det,obs).sum())
    from uuid import uuid4
    from datetime import datetime, timezone
    dest=ROOT/"research_data"/f"distance_{distance}"/"simulations"
    dest.mkdir(parents=True,exist_ok=True)
    name=uuid4().hex
    record=dict(id=name,source="SIMULATION",status="complete",shots=shots,failures=failed,probability=failed/shots,
                interval=wilson(failed,shots),distance=distance,rounds=rounds,pipeline="Stim",basis=basis,
                decoder=decoder,twirling=False,settings=data,detector_rates=det.mean(0).tolist(),
                date=datetime.now(timezone.utc).isoformat(),file=(dest/f"{name}.json").relative_to(ROOT).as_posix())
    (dest/f"{name}.json").write_text(json.dumps(record),encoding="utf-8")
    return record

def geometry(distance):
    c=make_stim_circuit(distance,1)
    coords=c.get_final_qubit_coordinates()
    edges=set()
    types={}
    layers={}
    layer=0
    for op in c:
        if op.name!="CX":
            continue
        q=[t.value for t in op.targets_copy()]
        for a,b in zip(q[::2],q[1::2]):
            edges.add(tuple(sorted((a,b))))
            layers[f"{min(a,b)}-{max(a,b)}"]=layer
            types[a]="data" if all(int(n)%2 for n in coords[a]) else "X"
            types[b]="data" if all(int(n)%2 for n in coords[b]) else "Z"
        layer+=1
    return dict(nodes=[dict(id=q,x=x,y=y,type=types[q]) for q,(x,y) in coords.items()],edges=sorted(edges),layers=layers)

def inspect_shot(record, index):
    import stim
    import numpy as np
    from internal_helpers import counts_to_measurement_array
    from archive import ROOT
    manifest=read(ARCHIVE/"manifest.json")
    def locate(name):
        if name in manifest:
            return ARCHIVE/manifest[name]["file"]
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT/"research_data"):
            raise ValueError("Source file unavailable")
        return path
    if not record.get("raw") or not record.get("model"):
        raise ValueError("Shot measurements unavailable")
    if not 0<=index<record["shots"]:
        raise ValueError("Shot index out of range")
    path=locate(record["raw"])
    model=stim.Circuit.from_file(str(locate(record["model"])))
    if path.suffix==".npz":
        with np.load(path,allow_pickle=False) as data:
            raw=data["records"]
        if raw.ndim==3:
            raw=raw[record["blocks"]].reshape(-1,model.num_measurements)
        order="saved array order"
    else:
        payload=read(path)
        raw=counts_to_measurement_array(payload.get("counts",payload),model.num_measurements,record["shots"])
        order="grouped bitstring counts, acquisition order unavailable"
    det,obs=model.compile_m2d_converter().convert(measurements=raw,separate_observables=True)
    coordinates=model.get_detector_coordinates()
    prediction=None
    if record["decoder"] in ("plain","correlated"):
        decoder=record["decoder"]
        prediction=bool(matcher(model,decoder).decode_batch(det[index:index+1],enable_correlations=decoder=="correlated")[0,0])
    return dict(order=order,events=[coordinates[i] for i,flag in enumerate(det[index]) if flag],
                rates=det.mean(0).tolist(), weights=np.bincount(det.sum(1).astype(int)).tolist(),
                coordinates=list(coordinates.values()),observable=bool(obs[index,0]),prediction=prediction)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(DESIGN),**kwargs)

    def respond(self,data,status=200):
        raw=json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        url=urlparse(self.path)
        path=url.path
        if path=="/api/health":
            return self.respond({"application":"QuantumTN"})
        if path in ("/api/geometry/3","/api/geometry/5"):
            return self.respond(geometry(int(path[-1])))
        if path=="/api/topology":
            f=ROOT/"research_data/hardware_characterization/topology.json"
            return self.respond(read(f) if f.exists() else {})
        if path=="/api/raw":
            key=parse_qs(url.query).get("record",[""])[0]
            record=next((r for r in archive_database()["records"] if r["id"]==key),None)
            if not record or not record.get("raw"):
                return self.send_error(404)
            rel=record["raw"]
            entry=read(ARCHIVE/"manifest.json").get(rel)
            file=(ARCHIVE/entry["file"] if entry else ROOT/rel).resolve()
            if not file.is_relative_to(ROOT/"research_data") or not file.is_file():
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type","application/octet-stream")
            self.send_header("Content-Disposition",f'attachment; filename="{file.name}"')
            self.send_header("Content-Length",str(file.stat().st_size))
            self.end_headers()
            with file.open("rb") as source:
                self.copyfile(source,self.wfile)
            return
        if path=="/api/records":
            db=archive_database()
            for distance in (3,5):
                for p in (ROOT/f"research_data/distance_{distance}/simulations").glob("*.json"):
                    db["records"].append(read(p))
            f=ROOT/"research_data/hardware_characterization/topology.json"
            if f.exists():
                db["topology"]=read(f)
            fit=ROOT/"research_data/distance_5/validation_fits.json"
            if fit.exists():
                db["simulation_fits"]=read(fit)
            pilot=ROOT/"research_data/distance_5/routed_hardware"
            job=pilot/"job-r3.json"
            if job.exists():
                db["pilot"]=dict(read(job),status="submitted")
                execution=pilot/"execution.json"
                if execution.exists():
                    db["pilot"].update(read(execution))
                if (pilot/"errors-r3.json").exists():
                    db["pilot"]["status"]="complete"
                if db["pilot"]["status"]!="complete":
                    db["records"].append(dict(
                        id="emerald-distance5-routed-pilot",source="FAILED_OR_INCOMPLETE",
                        status=db["pilot"]["status"],job=db["pilot"]["job_id"],backend="Emerald",
                        calibration=db["pilot"]["calibration"],distance=5,rounds=3,basis="Z",
                        pipeline="qiskit",twirling=False,shots=None,failures=None,probability=None))
            return self.respond(db)
        # Static files are explicitly allowlisted.
        if path not in ("/","/index.html","/style.css","/app.js","/experiments.json"):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path not in ("/api/simulate","/api/shot"):
            return self.send_error(404)
        try:
            length=int(self.headers.get("Content-Length",0))
            if not 0<length<=4096:
                raise ValueError("Invalid request length")
            data=json.loads(self.rfile.read(length))
            if self.path=="/api/shot":
                record=next((r for r in archive_database()["records"] if r["id"]==data["id"]),None)
                if not record:
                    raise ValueError("Unknown archive record")
                return self.respond(inspect_shot(record,int(data["index"])))
            return self.respond(simulate(data))
        except (ValueError,TypeError,KeyError,OSError) as error:
            return self.respond({"error":str(error)},400)

if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()
