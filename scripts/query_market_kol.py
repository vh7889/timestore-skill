import argparse
import json
import tomllib

import requests
from log_utils import start_run_logging


API_MARKET = "https://api.timestore.vip/issuer/market"


def load_auth_token(config_path: str) -> str:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)
    token = str(raw.get("auth_token", "")).strip()
    if not token:
        raise ValueError("config.auth_token is empty")
    return token


def build_headers(auth_token: str) -> dict:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "device": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
        "language": "zh-CN",
        "mate-auth": auth_token,
        "platform": "h5",
        "priority": "u=1, i",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }


def main():
    parser = argparse.ArgumentParser(description="Query TimeStore market KOL list")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--type", default="", help="Query param: type (default empty, i.e. type=)")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    token = load_auth_token(args.config)
    headers = build_headers(token)

    params = {"type": args.type}
    resp = requests.get(API_MARKET, headers=headers, params=params, timeout=10, verify=False)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("code") != 200:
        print(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(1)

    items = payload.get("data") or []
    print(f"count={len(items)}")

    for item in items:
        issuer_id = item.get("id")
        name = item.get("issuerName", "")
        status = item.get("issuerStatus")
        last_price = item.get("issuerLastPrice")
        mode_type = item.get("modeType")
        print(
            f"id={issuer_id} | issuerName={name} | issuerStatus={status} | issuerLastPrice={last_price} | modeType={mode_type}"
        )

    if args.raw:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    start_run_logging("query_market_kol")
    main()
