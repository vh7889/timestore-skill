import argparse
import json
import tomllib
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from log_utils import start_run_logging


API_MAX_SELL = "https://api.timestore.vip/issuerOrder/maxSell"
API_CONFIRM_SELL = "https://api.timestore.vip/issuerOrder/confirmSell"


def load_config(config_path: str) -> dict:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required = ["auth_token", "issuer_id", "feishu_url"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return {
        "auth_token": str(raw["auth_token"]),
        "issuer_id": int(raw["issuer_id"]),
        "feishu_url": str(raw["feishu_url"]),
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


def parse_decimal(v: str) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Invalid decimal value: {v}")


def send_feishu(webhook: str, text: str, verify_ssl: bool):
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "TIMESTORE 指定秒数卖出结果"},
                "template": "orange",
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
    parser = argparse.ArgumentParser(description="Sell by fixed volume: maxSell then confirmSell")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--volume", required=True, help="Volume(seconds) to sell, e.g. 100")
    parser.add_argument("--raw", action="store_true", help="Print raw API responses")
    args = parser.parse_args()

    cfg = load_config(args.config)
    headers = build_headers(cfg["auth_token"])
    verify_ssl = cfg["verify_ssl"]

    volume = parse_decimal(args.volume)

    r1 = requests.get(
        API_MAX_SELL,
        params={"issuerId": cfg["issuer_id"], "volume": str(volume)},
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    r1.raise_for_status()
    max_sell_data = r1.json()

    if max_sell_data.get("code") != 200:
        msg = f"maxSell失败: {json.dumps(max_sell_data, ensure_ascii=False)}"
        print(msg)
        send_feishu(cfg["feishu_url"], msg, verify_ssl)
        raise SystemExit(1)

    amount = max_sell_data.get("data", {}).get("amount")
    amount_dec = parse_decimal(amount)
    print(f"volume={volume}")
    print(f"maxSell.amount={amount_dec}")

    payload = {
        "expectAmount": str(amount_dec),
        "issuerId": cfg["issuer_id"],
        "volume": str(volume),
    }
    r2 = requests.post(API_CONFIRM_SELL, headers=headers, json=payload, timeout=10, verify=verify_ssl)
    r2.raise_for_status()
    confirm_data = r2.json()

    print(json.dumps(confirm_data, ensure_ascii=False))
    report = (
        f"**issuer_id:** {cfg['issuer_id']}\\n"
        f"**volume:** {volume}\\n"
        f"**expectAmount(来自maxSell):** {amount_dec}\\n"
        f"**confirmSell结果:** `{json.dumps(confirm_data, ensure_ascii=False)}`"
    )
    send_feishu(cfg["feishu_url"], report, verify_ssl)

    if args.raw:
        print("[raw] maxSell:")
        print(json.dumps(max_sell_data, ensure_ascii=False, indent=2))
        print("[raw] confirmSell:")
        print(json.dumps(confirm_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    start_run_logging("sell_by_volume_once")
    main()
