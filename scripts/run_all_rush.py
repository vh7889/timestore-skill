import argparse
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_MAP = {
    "rush": "rush_threshold.py",
    "rush_after_open": "rush_after_open.py",
    "bruteforce": "rush_bruteforce.py",
}


def parse_modes(raw: str):
    modes = [x.strip() for x in raw.split(",") if x.strip()]
    invalid = [m for m in modes if m not in SCRIPT_MAP]
    if invalid:
        raise ValueError(f"Unsupported modes: {', '.join(invalid)}")
    if not modes:
        raise ValueError("No mode selected")
    return modes


def main():
    parser = argparse.ArgumentParser(description="Run multiple TimeStore rush modes together")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument(
        "--modes",
        default="rush,rush_after_open,bruteforce",
        help="Comma-separated modes: rush,rush_after_open,bruteforce",
    )
    args = parser.parse_args()

    modes = parse_modes(args.modes)
    scripts_dir = Path(__file__).resolve().parent

    procs = []
    try:
        for mode in modes:
            script_name = SCRIPT_MAP[mode]
            script_path = scripts_dir / script_name
            cmd = [sys.executable, str(script_path), "--config", args.config]
            proc = subprocess.Popen(cmd)
            procs.append((mode, proc))
            print(f"[start] mode={mode} pid={proc.pid}")

        while True:
            alive = 0
            for mode, proc in procs:
                code = proc.poll()
                if code is None:
                    alive += 1
                elif code != 0:
                    print(f"[exit] mode={mode} code={code}")
            if alive == 0:
                print("[done] all processes exited")
                return
            time.sleep(1)
    except KeyboardInterrupt:
        print("[stop] Ctrl+C received, terminating child processes...")
    finally:
        for _, proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for _, proc in procs:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
