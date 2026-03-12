import argparse
import json
import time
import tomllib
from datetime import datetime

import requests

from log_utils import start_run_logging


API_MARKET = "https://api.timestore.vip/issuer/market"


def load_config(config_path: str) -> dict:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required = ["auth_token", "feishu_url", "issuer_id"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return {
        "auth_token": str(raw["auth_token"]),
        "feishu_url": str(raw["feishu_url"]),
        "issuer_id": int(raw["issuer_id"]),
        "market_type": str(raw.get("market_type", 0)),
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


def send_feishu(webhook: str, issuer_id: int, issuer_status, verify_ssl: bool):
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "TIMESTORE issuerStatus 变更提醒"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"**issuer_id:** {issuer_id}\n"
                            f"**issuerStatus:** {issuer_status}\n"
                            f"**规则:** issuerStatus != 1"
                        ),
                    },
                }
            ],
        },
    }
    resp = requests.post(webhook, json=payload, timeout=10, verify=verify_ssl)
    print(f"[feishu] status={resp.status_code}")


def fetch_issuer_status(headers: dict, issuer_id: int, market_type: str, verify_ssl: bool):
    resp = requests.get(
        API_MARKET,
        params={"type": market_type},
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"market query failed: {json.dumps(payload, ensure_ascii=False)}")

    for item in payload.get("data", []):
        if item.get("id") == issuer_id:
            return item.get("issuerStatus"), item, payload
    return None, None, payload


def main():
    parser = argparse.ArgumentParser(description="Monitor issuerStatus and alert when status != 1")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--issuer-id", type=int, default=None, help="Override config issuer_id")
    parser.add_argument("--interval", type=float, default=15, help="Polling interval seconds, default 15")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response on each check")
    args = parser.parse_args()

    cfg = load_config(args.config)
    issuer_id = args.issuer_id if args.issuer_id is not None else cfg["issuer_id"]
    headers = build_headers(cfg["auth_token"])

    while True:
        issuer_status, item, payload = fetch_issuer_status(
            headers, issuer_id, cfg["market_type"], cfg["verify_ssl"]
        )
        print(f"issuer_id={issuer_id}")
        print(f"issuerStatus={issuer_status}")

        if args.raw:
            if item is not None:
                print(json.dumps(item, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))

        if issuer_status is None:
            print("issuer not found in market list")
        elif issuer_status != 1:
            send_feishu(cfg["feishu_url"], issuer_id, issuer_status, cfg["verify_ssl"])
            return

        if args.once:
            return

        time.sleep(args.interval)


if __name__ == "__main__":
    start_run_logging("monitor_issuer_status")
    main()
