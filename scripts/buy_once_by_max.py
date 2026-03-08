import argparse
import json
import tomllib
from datetime import datetime

import requests

from log_utils import start_run_logging


API_MAX_BUY = "https://api.timestore.vip/issuerOrder/maxBuy"
API_CONFIRM_BUY = "https://api.timestore.vip/issuerOrder/confirmBuy"


def load_config(config_path: str) -> dict:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required = ["auth_token", "feishu_url", "issuer_id", "amount"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return {
        "auth_token": str(raw["auth_token"]),
        "feishu_url": str(raw["feishu_url"]),
        "issuer_id": int(raw["issuer_id"]),
        "amount": float(raw["amount"]),
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
    }


def send_feishu(webhook: str, text: str, verify_ssl: bool):
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "TIMESTORE 单次直买结果"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n{text}",
                    },
                }
            ],
        },
    }
    resp = requests.post(webhook, json=payload, timeout=10, verify=verify_ssl)
    print(f"[feishu] status={resp.status_code}")


def main():
    parser = argparse.ArgumentParser(description="One-shot buy: maxBuy then confirmBuy")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--raw", action="store_true", help="Print raw API responses")
    args = parser.parse_args()

    cfg = load_config(args.config)
    headers = build_headers(cfg["auth_token"])
    verify_ssl = cfg["verify_ssl"]

    max_buy_url = f"{API_MAX_BUY}?issuerId={cfg['issuer_id']}&amount={cfg['amount']}"
    r1 = requests.get(max_buy_url, headers=headers, timeout=10, verify=verify_ssl)
    r1.raise_for_status()
    max_buy_data = r1.json()

    if max_buy_data.get("code") != 200:
        msg = f"maxBuy失败: {json.dumps(max_buy_data, ensure_ascii=False)}"
        print(msg)
        send_feishu(cfg["feishu_url"], msg, verify_ssl)
        raise SystemExit(1)

    expect_volume = int(max_buy_data["data"]["estimateVolume"])
    print(f"estimateVolume={expect_volume}")

    confirm_payload = {
        "amount": cfg["amount"],
        "issuerId": cfg["issuer_id"],
        "expectVolume": expect_volume,
    }
    r2 = requests.post(API_CONFIRM_BUY, headers=headers, json=confirm_payload, timeout=10, verify=verify_ssl)
    r2.raise_for_status()
    confirm_data = r2.json()

    result_text = (
        f"**issuer_id:** {cfg['issuer_id']}\\n"
        f"**amount:** {cfg['amount']}\\n"
        f"**expectVolume(来自maxBuy):** {expect_volume}\\n"
        f"**confirmBuy结果:** `{json.dumps(confirm_data, ensure_ascii=False)}`"
    )
    print(json.dumps(confirm_data, ensure_ascii=False))
    send_feishu(cfg["feishu_url"], result_text, verify_ssl)

    if args.raw:
        print("[raw] maxBuy:")
        print(json.dumps(max_buy_data, ensure_ascii=False, indent=2))
        print("[raw] confirmBuy:")
        print(json.dumps(confirm_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    start_run_logging("buy_once_by_max")
    main()
