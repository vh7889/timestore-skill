import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import ssl
import tomllib

import aiohttp
from aiohttp import TCPConnector


API_MARKET = "https://api.timestore.vip/issuer/market"
API_MAX_BUY = "https://api.timestore.vip/issuerOrder/maxBuy"
API_CONFIRM_BUY = "https://api.timestore.vip/issuerOrder/confirmBuy"


@dataclass
class Config:
    auth_token: str
    feishu_url: str
    issuer_id: int
    amount: float
    expect_volume: int
    concurrency: int
    max_duration_seconds: int
    verify_ssl: bool
    open_check_interval_seconds: float
    market_type: int


def load_config(path: str) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    required = [
        "auth_token",
        "feishu_url",
        "issuer_id",
        "amount",
        "expect_volume",
        "concurrency",
        "max_duration_seconds",
    ]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    return Config(
        auth_token=str(raw["auth_token"]),
        feishu_url=str(raw["feishu_url"]),
        issuer_id=int(raw["issuer_id"]),
        amount=float(raw["amount"]),
        expect_volume=int(raw["expect_volume"]),
        concurrency=int(raw["concurrency"]),
        max_duration_seconds=int(raw["max_duration_seconds"]),
        verify_ssl=bool(raw.get("verify_ssl", False)),
        open_check_interval_seconds=float(raw.get("open_check_interval_seconds", 0.2)),
        market_type=int(raw.get("market_type", 0)),
    )


def build_headers(auth_token: str) -> dict:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "device": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N)",
        "language": "zh-CN",
        "mate-auth": auth_token,
        "platform": "h5",
        "priority": "u=1, i",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }


async def send_feishu_msg(session: aiohttp.ClientSession, url: str, text: str, ssl_ctx):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "TIMESTORE 下单成功"},
                "template": "green",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**结果:** {text}\\n**时间:** {now}",
                    },
                }
            ],
        },
    }
    async with session.post(url, json=payload, ssl=ssl_ctx) as resp:
        print(f"[feishu] status={resp.status}")


async def get_max_buy(session, cfg: Config, headers: dict, ssl_ctx):
    url = f"{API_MAX_BUY}?issuerId={cfg.issuer_id}&amount={cfg.amount}"
    async with session.get(url, headers=headers, ssl=ssl_ctx) as resp:
        data = await resp.json(content_type=None)
        if data.get("code") != 200:
            return None, data
        vol = int(data["data"]["estimateVolume"])
        return vol, data


async def confirm_buy(session, cfg: Config, headers: dict, expect_volume: int, ssl_ctx):
    payload = {
        "amount": cfg.amount,
        "issuerId": cfg.issuer_id,
        "expectVolume": int(expect_volume),
    }
    async with session.post(API_CONFIRM_BUY, headers=headers, json=payload, ssl=ssl_ctx) as resp:
        data = await resp.json(content_type=None)
        return data


async def wait_until_open(session, cfg: Config, headers: dict, ssl_ctx):
    print("[open-check] waiting for issuerStatus=2 ...")
    while True:
        try:
            url = f"{API_MARKET}?type={cfg.market_type}"
            async with session.get(url, headers=headers, ssl=ssl_ctx) as resp:
                data = await resp.json(content_type=None)
                for item in data.get("data", []):
                    if item.get("id") == cfg.issuer_id and item.get("issuerStatus") == 2:
                        print("[open-check] market opened")
                        return
        except Exception as e:
            print(f"[open-check] error: {e}")
        await asyncio.sleep(cfg.open_check_interval_seconds)


async def mode_query(session, cfg: Config, headers: dict, ssl_ctx):
    vol, raw = await get_max_buy(session, cfg, headers, ssl_ctx)
    if vol is None:
        print(json.dumps(raw, ensure_ascii=False))
        return False
    print(f"estimateVolume={vol}")
    return True


async def mode_rush_threshold_once(session, cfg: Config, headers: dict, ssl_ctx):
    try:
        vol, raw = await get_max_buy(session, cfg, headers, ssl_ctx)
        if vol is None:
            print(f"[rush] maxBuy non-200: {raw}")
            return False

        print(f"[rush] estimateVolume={vol}")
        if vol < cfg.expect_volume:
            return False

        result = await confirm_buy(session, cfg, headers, vol, ssl_ctx)
        print(f"[rush] confirm result: {result}")
        if result.get("code") == 200:
            await send_feishu_msg(
                session,
                cfg.feishu_url,
                f"issuer_id={cfg.issuer_id}, amount={cfg.amount}, volume={vol}",
                ssl_ctx,
            )
            return True
    except Exception as e:
        print(f"[rush] error: {e}")
    return False


async def mode_rush_threshold(session, cfg: Config, headers: dict, ssl_ctx):
    deadline = datetime.now() + timedelta(seconds=cfg.max_duration_seconds)
    while datetime.now() < deadline:
        tasks = [mode_rush_threshold_once(session, cfg, headers, ssl_ctx) for _ in range(cfg.concurrency)]
        results = await asyncio.gather(*tasks)
        if any(results):
            print("[rush] success, stop")
            return True
    print("[rush] timeout")
    return False


async def mode_bruteforce_once(session, cfg: Config, headers: dict, ssl_ctx):
    try:
        result = await confirm_buy(session, cfg, headers, cfg.expect_volume, ssl_ctx)
        print(f"[bruteforce] confirm result: {result}")
        if result.get("code") == 200:
            await send_feishu_msg(
                session,
                cfg.feishu_url,
                f"issuer_id={cfg.issuer_id}, amount={cfg.amount}, expect_volume={cfg.expect_volume}",
                ssl_ctx,
            )
            return True
    except Exception as e:
        print(f"[bruteforce] error: {e}")
    return False


async def mode_bruteforce(session, cfg: Config, headers: dict, ssl_ctx):
    deadline = datetime.now() + timedelta(seconds=cfg.max_duration_seconds)
    while datetime.now() < deadline:
        tasks = [mode_bruteforce_once(session, cfg, headers, ssl_ctx) for _ in range(cfg.concurrency)]
        results = await asyncio.gather(*tasks)
        if any(results):
            print("[bruteforce] success, keep running until timeout")
    print("[bruteforce] timeout")
    return False


async def run(mode: str, config_path: str):
    cfg = load_config(config_path)
    headers = build_headers(cfg.auth_token)

    ssl_ctx = None
    if not cfg.verify_ssl:
        ssl_ctx = False
    else:
        ssl_ctx = ssl.create_default_context()

    connector = TCPConnector(ssl=ssl_ctx)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        if mode == "query":
            await mode_query(session, cfg, headers, ssl_ctx)
            return

        if mode == "rush_after_open":
            await wait_until_open(session, cfg, headers, ssl_ctx)
            await mode_rush_threshold(session, cfg, headers, ssl_ctx)
            return

        if mode == "rush":
            await mode_rush_threshold(session, cfg, headers, ssl_ctx)
            return

        if mode == "bruteforce":
            await mode_bruteforce(session, cfg, headers, ssl_ctx)
            return

        raise ValueError(f"Unsupported mode: {mode}")


def parse_args():
    parser = argparse.ArgumentParser(description="TimeStore unified runner")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["query", "rush", "rush_after_open", "bruteforce"],
        help="query=查秒数, rush=阈值抢购, rush_after_open=开盘后阈值抢购, bruteforce=暴力抢购",
    )
    parser.add_argument(
        "--config",
        default="config/config.toml",
        help="Path to config TOML file",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args.mode, args.config))
