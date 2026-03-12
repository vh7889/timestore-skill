import argparse
import json
import tomllib

import requests
from log_utils import start_run_logging


API_TOTAL_ASSETS = "https://api.timestore.vip/balance/totalAssets?type=USDT"


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


def parse_balance(resp_json: dict):
    data = resp_json.get("data") or {}
    fund_account = data.get("fundAccount") or {}
    my_balance_list = fund_account.get("myBalanceList") or []
    position_account = data.get("positionAccount") or {}
    position_valuation = position_account.get("valuationCurrency")

    if not my_balance_list:
        return None, position_valuation, resp_json

    # User requirement: first myBalanceList item balanceValue is the balance.
    first = my_balance_list[0] or {}
    return first.get("balanceValue"), position_valuation, resp_json


def main():
    parser = argparse.ArgumentParser(description="Query TimeStore USDT balance")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    token = load_auth_token(args.config)
    headers = build_headers(token)

    resp = requests.get(API_TOTAL_ASSETS, headers=headers, timeout=10, verify=False)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("code") != 200:
        print(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(1)

    balance, position_valuation, full_json = parse_balance(payload)
    if balance is None:
        print("balanceValue not found in fundAccount.myBalanceList[0]")
        if args.raw:
            print(json.dumps(full_json, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    print(f"balanceValue={balance}")
    print(f"positionAccount.valuationCurrency={position_valuation}")
    if args.raw:
        print(json.dumps(full_json, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    start_run_logging("query_balance")
    main()
