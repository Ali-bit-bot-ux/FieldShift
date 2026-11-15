"""Start the local Python API and the Next.js planner together."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3001)
    parser.add_argument("--api-port", type=int, default=8000)
    args = parser.parse_args()
    node = shutil.which("node")
    next_bin = WEB / "node_modules/next/dist/bin/next"
    if not node or not next_bin.is_file():
        parser.exit(1, "Install Node.js and run npm ci in web first.\n")
    env = dict(os.environ, FIELDSHIFT_DATA_MODE="api",
               FIELDSHIFT_API_URL=f"http://127.0.0.1:{args.api_port}/api/recommendation")
    servers = []
    try:
        servers.append(subprocess.Popen([sys.executable, "-m", "uvicorn",
            "modules.fieldshift_api:app", "--host", "127.0.0.1", "--port", str(args.api_port)], cwd=ROOT))
        servers.append(subprocess.Popen([node, str(next_bin), "dev", "--webpack", "--hostname",
            "127.0.0.1", "--port", str(args.port)], cwd=WEB, env=env))
        while all(server.poll() is None for server in servers):
            time.sleep(0.3)
        return next(server.returncode for server in servers if server.poll() is not None)
    except KeyboardInterrupt:
        return 0
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
        for server in servers:
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    sys.exit(main())
