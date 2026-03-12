import argparse
import json
import time
import tomllib
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from log_utils import start_run_logging


API_POSITION_INFO = "https://api.timestore.vip/position/info"
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
        "sell_min_accept_amount": Decimal(str(raw.get("sell_min_accept_amount", 2000))),
        "sell_check_interval_seconds": float(raw.get("sell_check_interval_seconds", 1)),
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


def send_feishu(webhook: str, text: str, verify_ssl: bool):
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "TIMESTORE 卖出结果"},
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


def get_available_volume(headers: dict, issuer_id: int, verify_ssl: bool):
    resp = requests.get(
        API_POSITION_INFO,
        params={"issuerId": issuer_id},
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"position/info failed: {json.dumps(payload, ensure_ascii=False)}")
    return payload.get("data", {}).get("availableVolume"), payload


def get_max_sell_amount(headers: dict, issuer_id: int, volume, verify_ssl: bool):
    resp = requests.get(
        API_MAX_SELL,
        params={"issuerId": issuer_id, "volume": volume},
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        return None, payload
    return payload.get("data", {}).get("amount"), payload


def confirm_sell(headers: dict, issuer_id: int, volume, expect_amount, verify_ssl: bool):
    payload = {
        "expectAmount": str(expect_amount),
        "issuerId": issuer_id,
        "volume": volume,
    }
    resp = requests.post(
        API_CONFIRM_SELL,
        headers=headers,
        json=payload,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    return resp.json()


def parse_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Sell all when maxSell reaches target amount")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument(
        "--target-amount",
        type=str,
        default=None,
        help="Override config sell_min_accept_amount",
    )
    parser.add_argument(
        "--check-interval",
        type=float,
        default=None,
        help="Override config sell_check_interval_seconds",
    )
    parser.add_argument("--raw", action="store_true", help="Print raw API response on success")
    args = parser.parse_args()

    cfg = load_config(args.config)
    headers = build_headers(cfg["auth_token"])
    verify_ssl = cfg["verify_ssl"]

    target_amount = cfg["sell_min_accept_amount"]
    if args.target_amount is not None:
        override = parse_decimal(args.target_amount)
        if override is None:
            raise ValueError("--target-amount must be a valid number")
        target_amount = override

    check_interval = cfg["sell_check_interval_seconds"]
    if args.check_interval is not None:
        check_interval = args.check_interval

    volume, position_payload = get_available_volume(headers, cfg["issuer_id"], verify_ssl)
    if not volume:
        msg = "无法获取 availableVolume，退出"
        print(msg)
        send_feishu(cfg["feishu_url"], msg, verify_ssl)
        raise SystemExit(1)

    print(f"开始监听卖出机会，volume={volume}，最低目标 amount={target_amount}")

    while True:
        amount, max_sell_payload = get_max_sell_amount(headers, cfg["issuer_id"], volume, verify_ssl)
        amount_dec = parse_decimal(amount)
        print(f"[监测中] 当前 amount={amount}")

        if amount_dec is not None and amount_dec >= target_amount:
            print(f"达到预期，尝试卖出全部 volume={volume}, amount={amount_dec}")
            sell_result = confirm_sell(headers, cfg["issuer_id"], volume, amount_dec, verify_ssl)
            print(f"卖出结果: {json.dumps(sell_result, ensure_ascii=False)}")

            report = (
                f"**issuer_id:** {cfg['issuer_id']}\\n"
                f"**volume(全卖):** {volume}\\n"
                f"**target_amount:** {target_amount}\\n"
                f"**trigger_amount:** {amount_dec}\\n"
                f"**confirmSell结果:** `{json.dumps(sell_result, ensure_ascii=False)}`"
            )
            send_feishu(cfg["feishu_url"], report, verify_ssl)

            if args.raw:
                print("[raw] position/info:")
                print(json.dumps(position_payload, ensure_ascii=False, indent=2))
                print("[raw] maxSell(last):")
                print(json.dumps(max_sell_payload, ensure_ascii=False, indent=2))
                print("[raw] confirmSell:")
                print(json.dumps(sell_result, ensure_ascii=False, indent=2))
            return

        time.sleep(check_interval)


if __name__ == "__main__":
    start_run_logging("sell_all_when_target")
    main()
