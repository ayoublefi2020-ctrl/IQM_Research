import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

URL="http://127.0.0.1:8765"
def ready():
    try:
        with urllib.request.urlopen(URL+"/api/health",timeout=1) as req:
            return b"QuantumTN" in req.read()
    except OSError:
        return False

if ready():
    webbrowser.open(URL)
    raise SystemExit()
with subprocess.Popen([sys.executable,str(Path(__file__).with_name("server.py"))]) as server:
    try:
        for _ in range(80):
            if ready():
                webbrowser.open(URL)
                print("QuantumTN is running at",URL,"(Ctrl+C to stop)",flush=True)
                raise SystemExit(server.wait())
            if server.poll() is not None:
                raise SystemExit("Dashboard startup failed. See the error above.")
            time.sleep(.25)
        raise SystemExit("Dashboard took too long to start.")
    except KeyboardInterrupt:
        pass
    finally:
        if server.poll() is None:
            server.terminate()
