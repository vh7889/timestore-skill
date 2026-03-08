import argparse
import asyncio

from timestore_runner import run


def main():
    parser = argparse.ArgumentParser(description="Wait-open then threshold rush mode")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    args = parser.parse_args()
    asyncio.run(run("rush_after_open", args.config))


if __name__ == "__main__":
    main()
