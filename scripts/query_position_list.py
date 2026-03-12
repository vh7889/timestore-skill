import argparse
import json
import tomllib

import requests

from log_utils import start_run_logging


API_POSITION_LIST = "https://api.timestore.vip/position/list"


def load_config(config_path: str) -> dict:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required = ["auth_token"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return {
        "auth_token": str(raw["auth_token"]),
        "verify_ssl": bool(raw.get("verify_ssl", False)),
    }


def build_headers(auth_token: str) -> dict:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "device": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
        "language": "zh-CN",
        "mate-auth": auth_token,
        "platform": "h5",
        "referer": "https://web.timestore.vip/",
    }


def main():
    parser = argparse.ArgumentParser(description="Query TimeStore position list")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    cfg = load_config(args.config)
    headers = build_headers(cfg["auth_token"])

    resp = requests.get(API_POSITION_LIST, headers=headers, timeout=10, verify=cfg["verify_ssl"])
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("code") != 200:
        print(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(1)

    data = payload.get("data") or {}
    total_market_cap = data.get("totalMarketCap")
    total_hold_volume = data.get("totalHoldVolume")
    positions = data.get("positionList") or []

    print(f"totalMarketCap={total_market_cap}")
    print(f"totalHoldVolume={total_hold_volume}")
    print(f"positionCount={len(positions)}")

    for p in positions:
        print(
            " | ".join(
                [
                    f"issuerId={p.get('issuerId')}",
                    f"name={p.get('name')}",
                    f"holdVolume={p.get('holdVolume')}",
                    f"availableVolume={p.get('availableVolume')}",
                    f"marketCap={p.get('marketCap')}",
                    f"pnl={p.get('pnl')}",
                    f"roe={p.get('roe')}",
                ]
            )
        )

    if args.raw:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    start_run_logging("query_position_list")
    main()
