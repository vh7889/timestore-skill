import argparse
import json
import tomllib

import requests

from log_utils import start_run_logging


API_LP_WORKING = "https://api.timestore.vip/flow_pool/issuer_working"


def load_config(config_path: str) -> dict:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required = ["auth_token", "issuer_id"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return {
        "auth_token": str(raw["auth_token"]),
        "issuer_id": int(raw["issuer_id"]),
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
        "priority": "u=1, i",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "referer": "https://web.timestore.vip/",
    }


def main():
    parser = argparse.ArgumentParser(description="Query working LP by issuer")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--issuer-id", type=int, default=None, help="Override config issuer_id")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    cfg = load_config(args.config)
    issuer_id = args.issuer_id if args.issuer_id is not None else cfg["issuer_id"]
    headers = build_headers(cfg["auth_token"])

    resp = requests.get(
        API_LP_WORKING,
        params={"issuerId": issuer_id},
        headers=headers,
        timeout=10,
        verify=cfg["verify_ssl"],
    )
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("code") != 200:
        print(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(1)

    data = payload.get("data") or {}
    if not data:
        print(f"issuerId={issuer_id}")
        print("workingLP=none")
    else:
        print(f"issuerId={issuer_id}")
        print(f"lpId={data.get('id')}")
        print(f"issuerName={data.get('issuerName')}")
        print(f"amount={data.get('amount')}")
        print(f"second={data.get('second')}")
        print(f"surplusAmount={data.get('surplusAmount')}")
        print(f"surplusSecond={data.get('surplusSecond')}")
        print(f"status={data.get('status')}")

    if args.raw:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    start_run_logging("query_lp_working")
    main()
