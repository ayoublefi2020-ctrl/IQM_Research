import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uuid import UUID
from run_on_hardware import connect
folder=Path("research_data/distance_5/routed_hardware")
saved=json.loads((folder/"job-r3.json").read_text())
job=connect(use_metrics=False).client.get_job(UUID(saved["job_id"]))
status=getattr(job.status,"value",str(job.status))
info=dict(job_id=str(job.job_id),status=status)
print(info,flush=True)
if not (folder/"errors-r3.json").exists() and status!="completed":
    (folder/"execution.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
