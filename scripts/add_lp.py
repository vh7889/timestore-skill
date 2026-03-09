import argparse
import json
import tomllib
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from log_utils import start_run_logging


API_MAX_INJECTION = "https://api.timestore.vip/flow_pool/max_injection"
API_CALCULATE = "https://api.timestore.vip/flow_pool/calculate"
API_ADD_LP = "https://api.timestore.vip/flow_pool"


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
        "feishu_url": str(raw.get("feishu_url", "")),
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


def parse_decimal(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Invalid decimal value: {v}")


def send_feishu(webhook: str, title: str, text: str, verify_ssl: bool):
    if not webhook:
        return
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{text}",
                    },
                }
            ],
        },
    }
    resp = requests.post(webhook, json=payload, timeout=10, verify=verify_ssl)
    print(f"[feishu] status={resp.status_code}")


def get_max_injection(headers: dict, issuer_id: int, verify_ssl: bool):
    resp = requests.get(
        API_MAX_INJECTION,
        params={"issuerId": issuer_id},
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"max_injection failed: {json.dumps(payload, ensure_ascii=False)}")
    return payload


def calc_amount(headers: dict, issuer_id: int, seconds: int, verify_ssl: bool, calc_type: int = 1):
    resp = requests.get(
        API_CALCULATE,
        params={"issuerId": issuer_id, "numerical": seconds, "type": calc_type},
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"calculate failed: {json.dumps(payload, ensure_ascii=False)}")
    return parse_decimal(payload.get("data")), payload


def add_lp(headers: dict, issuer_id: int, seconds: int, amount: Decimal, verify_ssl: bool):
    body = {
        "issuerId": str(issuer_id),
        "poolAmount": float(amount),
        "poolSecond": str(seconds),
    }
    resp = requests.post(API_ADD_LP, headers=headers, json=body, timeout=10, verify=verify_ssl)
    resp.raise_for_status()
    return resp.json(), body


def main():
    parser = argparse.ArgumentParser(description="Add TimeStore LP (max_injection -> calculate -> flow_pool)")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument(
        "--mode",
        choices=["max", "calc", "submit", "full"],
        default="full",
        help="max=只查最大可加, calc=只算金额, submit=只提交LP, full=三步连跑",
    )
    parser.add_argument("--issuer-id", type=int, default=None, help="Override issuer_id in config")
    parser.add_argument(
        "--pool-second",
        type=int,
        default=None,
        help="LP seconds to add. Omit to use max_injection.data.realVolume",
    )
    parser.add_argument(
        "--pool-amount",
        type=str,
        default=None,
        help="Only for mode=submit. Explicit poolAmount to submit",
    )
    parser.add_argument("--type", type=int, default=1, help="calculate API type param, default 1")
    parser.add_argument("--dry-run", action="store_true", help="Only query max_injection/calculate, skip add LP")
    parser.add_argument("--raw", action="store_true", help="Print raw API responses")
    args = parser.parse_args()

    cfg = load_config(args.config)
    issuer_id = args.issuer_id if args.issuer_id is not None else cfg["issuer_id"]
    headers = build_headers(cfg["auth_token"])
    verify_ssl = cfg["verify_ssl"]

    failure_notified = False
    try:
        if args.mode == "max":
            max_payload = get_max_injection(headers, issuer_id, verify_ssl)
            max_data = max_payload.get("data") or {}
            print(
                f"max_injection: issuerName={max_data.get('issuerName')} maxAmount={max_data.get('maxAmount')} "
                f"maxVolume={max_data.get('maxVolume')} realAmount={max_data.get('realAmount')} "
                f"realVolume={max_data.get('realVolume')}"
            )
            if args.raw:
                print(json.dumps(max_payload, ensure_ascii=False, indent=2))
            return

        if args.mode == "calc":
            if args.pool_second is None:
                raise ValueError("mode=calc requires --pool-second")
            if args.pool_second <= 0:
                raise ValueError("pool_second must be > 0")
            need_amount, calc_payload = calc_amount(headers, issuer_id, args.pool_second, verify_ssl, args.type)
            print(f"poolSecond={args.pool_second}")
            print(f"calculate.needAmount={need_amount}")
            if args.raw:
                print(json.dumps(calc_payload, ensure_ascii=False, indent=2))
            return

        if args.mode == "submit":
            if args.pool_second is None or args.pool_amount is None:
                raise ValueError("mode=submit requires --pool-second and --pool-amount")
            if args.pool_second <= 0:
                raise ValueError("pool_second must be > 0")
            pool_amount = parse_decimal(args.pool_amount)
            add_payload, body = add_lp(headers, issuer_id, args.pool_second, pool_amount, verify_ssl)
            print(f"add_lp.result={json.dumps(add_payload, ensure_ascii=False)}")
            if add_payload.get("code") != 200:
                fail = (
                    f"**issuer_id:** {issuer_id}\n"
                    f"**poolSecond:** {args.pool_second}\n"
                    f"**poolAmount:** {pool_amount}\n"
                    f"**失败结果:** `{json.dumps(add_payload, ensure_ascii=False)}`"
                )
                send_feishu(cfg["feishu_url"], "TIMESTORE 组LP失败", fail, verify_ssl)
                failure_notified = True
                raise RuntimeError(f"flow_pool submit failed: {json.dumps(add_payload, ensure_ascii=False)}")
            report = (
                f"**issuer_id:** {issuer_id}\n"
                f"**poolSecond:** {args.pool_second}\n"
                f"**poolAmount(手动传入):** {pool_amount}\n"
                f"**flow_pool请求体:** `{json.dumps(body, ensure_ascii=False)}`\n"
                f"**结果:** `{json.dumps(add_payload, ensure_ascii=False)}`"
            )
            send_feishu(cfg["feishu_url"], "TIMESTORE 组LP成功", report, verify_ssl)
            if args.raw:
                print(json.dumps(add_payload, ensure_ascii=False, indent=2))
            return

        # mode=full (default): max_injection -> calculate -> flow_pool
        max_payload = get_max_injection(headers, issuer_id, verify_ssl)
        max_data = max_payload.get("data") or {}
        max_volume = max_data.get("maxVolume")
        real_volume = max_data.get("realVolume")
        print(
            f"max_injection: issuerName={max_data.get('issuerName')} maxAmount={max_data.get('maxAmount')} "
            f"maxVolume={max_volume} realAmount={max_data.get('realAmount')} realVolume={real_volume}"
        )

        pool_second = args.pool_second
        if pool_second is None:
            pool_second = int(Decimal(str(real_volume)))
        if pool_second <= 0:
            raise ValueError("pool_second must be > 0")
        print(f"poolSecond={pool_second}")

        need_amount, calc_payload = calc_amount(headers, issuer_id, pool_second, verify_ssl, args.type)
        print(f"calculate.needAmount={need_amount}")

        if args.dry_run:
            print("dry-run enabled, skip add LP")
            return

        add_payload, body = add_lp(headers, issuer_id, pool_second, need_amount, verify_ssl)
        print(f"add_lp.result={json.dumps(add_payload, ensure_ascii=False)}")
        if add_payload.get("code") != 200:
            fail = (
                f"**issuer_id:** {issuer_id}\n"
                f"**poolSecond:** {pool_second}\n"
                f"**poolAmount:** {need_amount}\n"
                f"**失败结果:** `{json.dumps(add_payload, ensure_ascii=False)}`"
            )
            send_feishu(cfg["feishu_url"], "TIMESTORE 组LP失败", fail, verify_ssl)
            failure_notified = True
            raise RuntimeError(f"flow_pool submit failed: {json.dumps(add_payload, ensure_ascii=False)}")

        report = (
            f"**issuer_id:** {issuer_id}\n"
            f"**poolSecond:** {pool_second}\n"
            f"**poolAmount(来自calculate):** {need_amount}\n"
            f"**flow_pool请求体:** `{json.dumps(body, ensure_ascii=False)}`\n"
            f"**结果:** `{json.dumps(add_payload, ensure_ascii=False)}`"
        )
        send_feishu(cfg["feishu_url"], "TIMESTORE 组LP成功", report, verify_ssl)

        if args.raw:
            print("[raw] max_injection:")
            print(json.dumps(max_payload, ensure_ascii=False, indent=2))
            print("[raw] calculate:")
            print(json.dumps(calc_payload, ensure_ascii=False, indent=2))
            print("[raw] add_lp:")
            print(json.dumps(add_payload, ensure_ascii=False, indent=2))
    except Exception as e:
        if not failure_notified:
            send_feishu(
                cfg.get("feishu_url", ""),
                "TIMESTORE 组LP失败",
                f"**issuer_id:** {issuer_id}\n**错误:** `{str(e)}`",
                verify_ssl,
            )
        raise


if __name__ == "__main__":
    start_run_logging("add_lp")
    main()
