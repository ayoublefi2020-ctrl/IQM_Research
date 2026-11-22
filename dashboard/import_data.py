import json
from pathlib import Path
import numpy as np
from archive import ARCHIVE, ROOT
from qec_analysis import wilson

def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def validate_counts(shots, failures):
    if type(shots) is not int or type(failures) is not int or not 0 <= failures <= shots or shots == 0:
        raise ValueError("Invalid shot or logical failure count")

def register_execution(executions, key, shots):
    if key in executions:
        raise ValueError(f"Duplicate execution {key}")
    executions[key]=shots

def build():
    manifest = read(ARCHIVE / "manifest.json")
    files = {Path(k): ARCHIVE / v["file"] for k,v in manifest.items()}
    for folder in ("results/distance5_rate", "research_data/distance_5/routed_hardware", "research_data/distance_5/routing_followup", "research_data/distance_3/basis_pilot"):
        files.update({p.relative_to(ROOT):p for p in (ROOT/folder).rglob("*") if p.is_file()})
    records = []
    executions = {}
    def get(p, default=None):
        return read(files[p]) if p in files else default
    def add(source, settings, rounds, shots, failures, job=None, arm=None, raw=None, decoder=None, model=None, audit=None, variant=None):
        validate_counts(shots,failures)
        kind = "IQM_HARDWARE" if job else "SIMULATION"
        if job:
            key = (job, rounds, arm, variant)
            register_execution(executions,key,shots)
        record = dict(id=f"{source.as_posix()}:{rounds}:{arm}:{variant}",source=kind, status="complete",
                      distance=settings.get("distance",3), pipeline=settings.get("pipeline","Qiskit") if job else "Stim",
                      basis=settings.get("basis","Z"), rounds=rounds, shots=shots, failures=failures,
                      probability=failures/shots, interval=list(map(float,wilson(failures,shots))),
                      twirling=None if arm is None else arm=="twirl", decoder=decoder or settings.get("decoder"),
                      backend=settings.get("device","Emerald") if job else None,
                      calibration=settings.get("calibration"), mapping=settings.get("wire_names"), job=job,
                      raw=raw.as_posix() if raw in files else None, model=model.as_posix() if model in files else None,
                      audit=get(audit), variant=variant,
                      date=next((part[:8] for part in reversed(source.parts) if part.startswith("2026")),None),
                      file=source.as_posix())
        if job and not record["date"]:
            record["date"]="20261122" if "20261122" in str(source) else None
        records.append(record)
        return record
    for p in sorted(files):
        parent=p.parent
        settings=get(parent/"settings.json",{})
        if p.name.endswith("-blocks.json") and p.name.startswith("r"):
            tag=p.name.split("-")[0]
            job=get(parent/f"{tag}-job.json")
            if not job:
                continue
            raw=parent/f"{tag}-raw.npz"
            blocks=get(p)
            if raw in files:
                with np.load(files[raw],allow_pickle=False) as arrays:
                    shape=arrays["records"].shape
                if len(blocks)!=shape[0] or any(b["shots"]!=shape[1] for b in blocks):
                    raise ValueError(f"Raw/block shot mismatch: {p}")
            for arm in ("control","twirl"):
                selected=[b for b in blocks if b["arm"]==arm]
                if sum(b["shots"] for b in selected)!=settings["shots_per_arm"]:
                    raise ValueError(f"Arm shot mismatch: {p}")
                audit=get(parent/f"{tag}-audit.json",{})
                record=add(p,settings,int(tag[1:]),sum(b["shots"] for b in selected),
                           sum(b["errors"] for b in selected),job["id"],arm,raw,
                           model=parent/f"{tag}.stim")
                record["audit"]=audit.get("check")
                record["blocks"]=[i for i,pair in enumerate(audit.get("manifest",[])) if pair[0]==arm]
                decoder_sweep=get(parent.parent/"decoder_sweep.json",{})
                key=f'{settings["pipeline"]}_{tag}_characterized'
                if key in decoder_sweep:
                    k=decoder_sweep[key][arm]
                    records.append(dict(record,id=record["id"]+":characterized",failures=k,
                                        probability=k/record["shots"],decoder="BP+OSD characterized",
                                        interval=list(map(float,wilson(k,record["shots"])))))
        elif p.name=="decoded.json" and parent.name=="basis_pilot":
            meta=get(parent/"job.json")
            for basis,stats in get(p).items():
                raw=parent/f"{basis}-raw.npz"
                model=parent/f"{basis}.stim"
                with np.load(files[raw],allow_pickle=False) as data:
                    if data["records"].shape!=(meta["shots"],meta["audits"][basis]["measurement_keys"]):
                        raise ValueError(f"Basis pilot shot mismatch for {basis}")
                if stats["shots"]!=meta["shots"]:
                    raise ValueError(f"Decoded shot mismatch for {basis}")
                row=add(p,dict(meta,basis=basis,pipeline="qiskit"),meta["rounds"],stats["shots"],
                        stats["failures"],meta["job"],"control",raw,meta["decoder"],model,variant=basis)
                row["audit"]=meta["audits"][basis]
        elif p.name.startswith("errors-r") and parent.name in ("routed_hardware","routing_followup"):
            stats=get(p)
            meta=get(parent/"compile.json")
            raw=parent/"r3-raw.npz"
            with np.load(files[raw],allow_pickle=False) as arrays:
                if arrays["records"].shape!=(stats["shots"],97):
                    raise ValueError("Distance-5 raw shape mismatch")
            row=add(p,meta,3,stats["shots"],stats["failures"],stats["job_id"],"control",raw,
                    decoder=stats["decoder"],model=parent/"decoder-r3.stim")
            row.update(detector_rates=stats["detector_rates"],audit=meta,mapping=meta["initial_layout"])
            audit_name="pilot_audit.json" if parent.name=="routed_hardware" else "followup_audit.json"
            audit_path=ROOT/parent.parent/audit_name
            if audit_path.exists():
                checked=read(audit_path)
                if checked["job"]!=row["job"] or checked["archive_decode"]["failures"]!=row["failures"]:
                    raise ValueError(f"Routing analysis belongs to a different result: {p}")
                row.update(routed_redecode=checked["routed_redecode"],audit_file=audit_path.relative_to(ROOT).as_posix())
        elif p.name.startswith("errors-r"):
            r=int(p.stem.split("-r")[1])
            raw=parent/f"counts-r{r}.json"
            packet=get(raw,{})
            if not settings.get("simulate") and not packet:
                continue
            stats=get(p)
            counts=packet.get("counts")
            if counts and sum(counts.values())!=stats["shots"]:
                raise ValueError(f"Shot mismatch: {p}")
            job=packet.get("job_id") or get(parent/f"job-r{r}.json",{}).get("job_id")
            if packet and not job:
                continue
            meta=dict(settings, calibration=packet.get("calibration_set"))
            result=add(p,meta,r,stats["shots"],stats["failures"],job,raw=raw,
                       decoder=stats.get("decoder"),model=parent/f"decoder-r{r}.stim")
            result["detector_rates"]=stats.get("detector_rates")
        elif p.name=="scores.json" and "project_comparison" in str(p):
            for row in get(p)["rows"]:
                tag=f'{row["project"]}-r{row["rounds"]}'
                raw=parent/f"{tag}-counts.json"
                if sum(get(raw).values())!=row["shots"]:
                    raise ValueError(f"Shot mismatch: {raw}")
                add(p,settings,row["rounds"],row["shots"],row["bposd"],get(parent/"job.json")["id"],
                    raw=raw,decoder="BP+OSD",model=parent/f"{tag}.stim",variant=row["project"])
    return dict(schema_version=1,records=records,hardware_jobs=len({k[0] for k in executions}),
                hardware_shots=sum(executions.values()),source_files=len(manifest))

def write_database():
    db=build()
    destination=ROOT/"dashboard/experiments.json"
    temporary=destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(db,indent=2),encoding="utf-8")
    temporary.replace(destination)
    print(len(db["records"]),db["hardware_jobs"],db["hardware_shots"])

if __name__=="__main__":
    write_database()
