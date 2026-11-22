# QuantumTN on Windows

Double-click `START_IQM_DASHBOARD.cmd`. The launcher opens http://127.0.0.1:8765 in the default browser. If the dashboard is already running it opens the existing instance. Press Ctrl+C in the launcher window to stop the server.

If the virtual environment is missing, install Python 3.12 and run these commands in the project directory.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The demo uses local HTML, CSS, JavaScript and Python. It needs no hardware credentials or network connection after dependency installation. Use the section links in the header to walk through the experiment.

The archive uses the verified JSON snapshot. Rebuild it after importing a completed job.

```powershell
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe dashboard/import_data.py
.\.venv\Scripts\python.exe dashboard/validate_science.py --sweep
```

Use `dashboard/distance5_pilot.py --submit` only for the bounded live pilot. When a saved job ID exists, it reconnects to that job. The browser smoke test uses Edge and the optional `playwright-core` dependency installed to `%TEMP%/quantumtn-browser`.
