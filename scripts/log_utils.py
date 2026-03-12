import sys
from datetime import datetime
from pathlib import Path


class TimestampTee:
    def __init__(self, *streams):
        self.streams = streams
        self.at_line_start = True

    def _ts(self) -> str:
        return datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")

    def write(self, data):
        if not data:
            return 0

        parts = data.splitlines(keepends=True)
        for part in parts:
            out = part
            if self.at_line_start:
                out = self._ts() + out
            self.at_line_start = out.endswith("\n")
            for s in self.streams:
                s.write(out)
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
    sys.stdout = TimestampTee(old_stdout, log_file)
    sys.stderr = TimestampTee(old_stderr, log_file)

    print(f"[log] file={log_path}")
    return log_path
