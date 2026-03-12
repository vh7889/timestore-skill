import argparse
import json
import time
import tomllib
from datetime import datetime

import requests

from log_utils import start_run_logging


API_TIMELINE = "https://api.timestore.vip/timeline/mymblog"


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
        "post_monitor_uid": str(raw.get("post_monitor_uid", "")),
        "post_monitor_interval_seconds": float(raw.get("post_monitor_interval_seconds", 15)),
        "post_monitor_known_latest_id": str(raw.get("post_monitor_known_latest_id", "")),
        "post_monitor_known_latest_prefix": str(raw.get("post_monitor_known_latest_prefix", "")),
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


def send_feishu(webhook: str, post: dict, verify_ssl: bool):
    post_content = (post.get("postContent") or "").strip()
    first_line = post_content.splitlines()[0] if post_content else ""
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "TIMESTORE KOL 发新帖提醒"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"**uid:** {post.get('uid')}\n"
                            f"**post_id:** {post.get('id')}\n"
                            f"**nickName:** {post.get('nickName')}\n"
                            f"**ctime:** {post.get('ctimeStr')}\n"
                            f"**标题:** {first_line}\n"
                            f"**内容预览:** {post_content[:300]}"
                        ),
                    },
                }
            ],
        },
    }
    resp = requests.post(webhook, json=payload, timeout=10, verify=verify_ssl)
    print(f"[feishu] status={resp.status_code}")


def fetch_latest_post(headers: dict, uid: str, verify_ssl: bool):
    resp = requests.get(
        API_TIMELINE,
        params={
            "current": 1,
            "size": 10,
            "uid": uid,
            "id": 0,
            "screen": 0,
            "date": "",
        },
        headers=headers,
        timeout=10,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"timeline query failed: {json.dumps(payload, ensure_ascii=False)}")

    records = ((payload.get("data") or {}).get("records")) or []
    latest = records[0] if records else None
    return latest, payload


def is_new_post(post: dict, known_id: str, known_prefix: str) -> bool:
    if post is None:
        return False

    post_id = str(post.get("id") or "")
    post_content = (post.get("postContent") or "").strip()

    if known_id and post_id and post_id != known_id:
        return True

    if known_prefix and post_content and not post_content.startswith(known_prefix):
        return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Monitor KOL new post and send Feishu alert")
    parser.add_argument("--config", default="config/config.toml", help="Path to config TOML")
    parser.add_argument("--uid", default=None, help="Override config post_monitor_uid")
    parser.add_argument("--interval", type=float, default=None, help="Polling interval seconds")
    parser.add_argument("--known-id", default=None, help="Override config post_monitor_known_latest_id")
    parser.add_argument(
        "--known-prefix",
        default=None,
        help="Override config post_monitor_known_latest_prefix",
    )
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--raw", action="store_true", help="Print raw response")
    args = parser.parse_args()

    cfg = load_config(args.config)
    uid = args.uid if args.uid is not None else cfg["post_monitor_uid"]
    interval = args.interval if args.interval is not None else cfg["post_monitor_interval_seconds"]
    known_id = args.known_id if args.known_id is not None else cfg["post_monitor_known_latest_id"]
    known_prefix = (
        args.known_prefix if args.known_prefix is not None else cfg["post_monitor_known_latest_prefix"]
    )

    if not uid:
        raise ValueError("uid is required via config.post_monitor_uid or --uid")

    headers = build_headers(cfg["auth_token"])

    while True:
        latest_post, payload = fetch_latest_post(headers, uid, cfg["verify_ssl"])
        if latest_post is None:
            print(f"uid={uid}")
            print("latestPost=none")
        else:
            post_content = (latest_post.get("postContent") or "").strip()
            first_line = post_content.splitlines()[0] if post_content else ""
            print(f"uid={uid}")
            print(f"latestPostId={latest_post.get('id')}")
            print(f"latestPostTitle={first_line}")

        if args.raw:
            print(json.dumps(payload, ensure_ascii=False, indent=2))

        if is_new_post(latest_post, known_id, known_prefix):
            send_feishu(cfg["feishu_url"], latest_post, cfg["verify_ssl"])
            return

        if args.once:
            return

        time.sleep(interval)


if __name__ == "__main__":
    start_run_logging("monitor_kol_post")
    main()
