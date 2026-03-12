import argparse
import json
import tomllib
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from log_utils import start_run_logging


API_LP_CLOSED = "https://api.timestore.vip/flow_pool/closed"


def load_config(config_path: str) -> dict:
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required = ["auth_token", "feishu_url"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return {
        "auth_token": str(raw["auth_token"]),
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
        "priority": "u=1, i",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "referer": "https://web.timestore.vip/",
    }


def parse_decimal(v: str) -> Decimal:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Invalid proportion: {v}")
    if d <= 0 or d > 1:
        raise ValueError("proportion must be in (0, 1]")
    return d


def send_feishu(webhook: str, title: str, text: str, verify_ssl: bool):
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
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
    parser = argparse.ArgumentParser(description="Close (withdraw) LP by id")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--id", required=True, help="LP id from flow_pool/issuer_working")
    parser.add_argument("--proportion", default="1", help="Withdraw proportion in (0,1], default 1")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    cfg = load_config(args.config)
    headers = build_headers(cfg["auth_token"])
    proportion = parse_decimal(args.proportion)

    body = {"id": str(args.id), "proportion": float(proportion)}
    failure_notified = False
    try:
        resp = requests.post(API_LP_CLOSED, headers=headers, json=body, timeout=10, verify=cfg["verify_ssl"])
        resp.raise_for_status()
        payload = resp.json()

        print(f"request={json.dumps(body, ensure_ascii=False)}")
        print(f"result={json.dumps(payload, ensure_ascii=False)}")
        if payload.get("code") != 200:
            fail_report = (
                f"**lp_id:** {args.id}\\n"
                f"**proportion:** {proportion}\\n"
                f"**失败结果:** `{json.dumps(payload, ensure_ascii=False)}`"
            )
            send_feishu(cfg["feishu_url"], "TIMESTORE LP 提取失败", fail_report, cfg["verify_ssl"])
            failure_notified = True
            raise RuntimeError(f"close LP failed: {json.dumps(payload, ensure_ascii=False)}")

        report = (
            f"**lp_id:** {args.id}\\n"
            f"**proportion:** {proportion}\\n"
            f"**结果:** `{json.dumps(payload, ensure_ascii=False)}`"
        )
        send_feishu(cfg["feishu_url"], "TIMESTORE LP 提取成功", report, cfg["verify_ssl"])

        if args.raw:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as e:
        if not failure_notified:
            send_feishu(
                cfg["feishu_url"],
                "TIMESTORE LP 提取失败",
                f"**lp_id:** {args.id}\\n**proportion:** {proportion}\\n**错误:** `{str(e)}`",
                cfg["verify_ssl"],
            )
        raise


if __name__ == "__main__":
    start_run_logging("close_lp")
    main()
