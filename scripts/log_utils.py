import sys
from datetime import datetime
from pathlib import Path


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def start_run_logging(script_name: str) -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"{script_name}-{ts}.log"
    log_file = open(log_path, "a", encoding="utf-8")

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = Tee(old_stdout, log_file)
    sys.stderr = Tee(old_stderr, log_file)

    print(f"[log] file={log_path}")
    return log_path
