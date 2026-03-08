import argparse
import asyncio

from timestore_runner import run
from log_utils import start_run_logging


def main():
    parser = argparse.ArgumentParser(description="Bruteforce rush mode")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    args = parser.parse_args()
    asyncio.run(run("bruteforce", args.config))


if __name__ == "__main__":
    start_run_logging("rush_bruteforce")
    main()
