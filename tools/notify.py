#!/usr/bin/env python3
"""多通道交付 / 推送 — Telegram + 飞书自定义机器人 + 本地文件兜底。

设计理念（吸收自 JusticePlutus 的「可选增强 / 失败降级 / 零侵入」范式）：
  - 全部通道走环境变量配置；**零配置时行为不变**：不报错、只把内容落到本地文件。
  - 任一通道未配置 → 静默跳过该通道，不影响其它通道与主流程。
  - 飞书优先发交互卡片，失败回退纯文本；超长消息自动按平台上限拆分多条发送。
  - 网络层用系统 curl（零第三方依赖），便于在测试中 mock，不打真实网络。

环境变量：
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID      # Telegram 通道
  FEISHU_WEBHOOK                            # 飞书自定义机器人 Webhook
  FEISHU_SECRET                             # （可选）飞书加签密钥
  BERKSHIRE_NOTIFY_DIR                      # 本地兜底目录，默认 reports/notifications

用法（CLI）：
  python3 tools/notify.py channels                          # 查看通道状态
  python3 tools/notify.py send --title "标题" --text "正文"
  python3 tools/notify.py send --title "标题" --file reports/x.md
  echo "正文" | python3 tools/notify.py send --title "标题"
  # 仅指定通道：--channels telegram,feishu ；强制本地落地：--local
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from datetime import datetime

_TIMEOUT = 15
_STATUS_SENTINEL = "__HTTP_STATUS__"

# 各平台单条消息长度上限（保守取值，留余量）。
TELEGRAM_LIMIT = 3800
FEISHU_LIMIT = 3000


def _log_warn(msg: str) -> None:
    sys.stderr.write(f"[notify] WARNING: {msg}\n")


def _curl_post_json(url, payload, timeout=_TIMEOUT):
    """用 curl 发 POST JSON，返回 (status_code:int, body:str)。

    网络异常/超时不抛出，返回 (0, 错误信息)，由上层判定失败并降级。
    """
    body = json.dumps(payload, ensure_ascii=False)
    try:
        result = subprocess.run(
            ["/usr/bin/curl", "-s", "--noproxy", "*", "-X", "POST",
             "-H", "Content-Type: application/json",
             "-w", f"\n{_STATUS_SENTINEL}%{{http_code}}",
             "-d", body, url],
            capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 0, f"timeout (>{timeout}s)"
    except Exception as e:  # pragma: no cover - 防御性
        return 0, f"{type(e).__name__}: {e}"
    if result.returncode != 0:
        return 0, f"curl exit {result.returncode}: {result.stderr.decode('utf-8', 'replace')[:200]}"
    out = result.stdout.decode("utf-8", "replace")
    status = 0
    if _STATUS_SENTINEL in out:
        out, _, code = out.rpartition(_STATUS_SENTINEL)
        try:
            status = int(code.strip())
        except ValueError:
            status = 0
    return status, out.strip()


def _split_text(text, limit):
    """按上限把文本拆成多段，尽量在换行处切分。"""
    text = text or ""
    if len(text) <= limit:
        return [text] if text else [""]
    parts, buf = [], ""
    for line in text.splitlines(keepends=True):
        # 单行就超限：硬切。
        while len(line) > limit:
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = line
        else:
            buf += line
    if buf:
        parts.append(buf)
    return parts


def _env(name):
    return os.environ.get(name, "").strip()


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def telegram_available():
    if _env("TELEGRAM_BOT_TOKEN") and _env("TELEGRAM_CHAT_ID"):
        return True, ""
    return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 未配置"


def send_telegram(title, text):
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    full = f"*{title}*\n\n{text}" if title else text
    chunks = _split_text(full, TELEGRAM_LIMIT)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent = 0
    for chunk in chunks:
        status, body = _curl_post_json(url, {
            "chat_id": chat_id, "text": chunk,
            "parse_mode": "Markdown", "disable_web_page_preview": True,
        })
        if status != 200:
            return {"channel": "telegram", "ok": False, "parts": sent,
                    "error": f"HTTP {status}: {body[:200]}"}
        sent += 1
    return {"channel": "telegram", "ok": True, "parts": sent, "error": None}


# ---------------------------------------------------------------------------
# 飞书自定义机器人（优先卡片，失败回退文本，长消息拆分）
# ---------------------------------------------------------------------------
def feishu_available():
    if _env("FEISHU_WEBHOOK"):
        return True, ""
    return False, "FEISHU_WEBHOOK 未配置"


def _feishu_sign(secret, timestamp):
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"),
                      digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _feishu_security(payload):
    """如配置 FEISHU_SECRET 则附加加签字段（原地修改 payload）。"""
    secret = _env("FEISHU_SECRET")
    if secret:
        ts = str(int(time.time()))
        payload["timestamp"] = ts
        payload["sign"] = _feishu_sign(secret, ts)
    return payload


def _feishu_post(payload):
    url = _env("FEISHU_WEBHOOK")
    status, body = _curl_post_json(url, _feishu_security(payload))
    if status != 200:
        return False, f"HTTP {status}: {body[:200]}"
    # 飞书业务码：成功 code==0（或返回 StatusCode==0）。
    try:
        data = json.loads(body)
        code = data.get("code", data.get("StatusCode", 0))
        if code not in (0, "0"):
            return False, f"feishu code={code}: {data.get('msg', body[:120])}"
    except (ValueError, AttributeError):
        pass
    return True, None


def _feishu_card(title, chunk):
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title or "Berkshire AI"},
                "template": "blue",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": chunk}},
            ],
        },
    }


def _feishu_text(title, chunk):
    content = f"{title}\n{chunk}" if title else chunk
    return {"msg_type": "text", "content": {"text": content}}


def send_feishu(title, text):
    chunks = _split_text(text, FEISHU_LIMIT)
    sent, used_text_fallback = 0, False
    for i, chunk in enumerate(chunks):
        part_title = title if i == 0 else f"{title} (续 {i + 1})"
        ok, err = _feishu_post(_feishu_card(part_title, chunk))
        if not ok:
            # 卡片失败 → 回退纯文本。
            ok, err = _feishu_post(_feishu_text(part_title, chunk))
            used_text_fallback = used_text_fallback or ok
        if not ok:
            return {"channel": "feishu", "ok": False, "parts": sent,
                    "error": err}
        sent += 1
    return {"channel": "feishu", "ok": True, "parts": sent,
            "error": None, "text_fallback": used_text_fallback}


# ---------------------------------------------------------------------------
# 本地文件兜底
# ---------------------------------------------------------------------------
def _notify_dir():
    return _env("BERKSHIRE_NOTIFY_DIR") or os.path.join("reports", "notifications")


def write_local(title, text):
    d = _notify_dir()
    os.makedirs(d, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c for c in (title or "notify") if c.isalnum() or c in "-_ ").strip()
    safe = (safe or "notify").replace(" ", "_")[:40]
    path = os.path.join(d, f"{ts}-{safe}.md")
    with open(path, "w", encoding="utf-8") as f:
        if title:
            f.write(f"# {title}\n\n")
        f.write(text or "")
        f.write("\n")
    return path


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------
_CHANNELS = {
    "telegram": (telegram_available, send_telegram),
    "feishu": (feishu_available, send_feishu),
}


def channel_status(channels=None):
    names = channels or list(_CHANNELS)
    out = []
    for name in names:
        if name not in _CHANNELS:
            out.append({"channel": name, "available": False,
                        "reason": "未知通道"})
            continue
        avail, reason = _CHANNELS[name][0]()
        out.append({"channel": name, "available": avail,
                    "reason": reason or "ok"})
    return out


def notify(title, text, channels=None, always_local=False):
    """向已配置通道推送；零配置或全部失败时落地本地文件，绝不抛异常。

    返回 {channels:[...], local_file: path|None, delivered: bool}
    """
    names = channels or list(_CHANNELS)
    results, delivered = [], False
    for name in names:
        if name not in _CHANNELS:
            results.append({"channel": name, "ok": False,
                            "skipped": True, "error": "未知通道"})
            continue
        avail, reason = _CHANNELS[name][0]()
        if not avail:
            results.append({"channel": name, "ok": False,
                            "skipped": True, "error": reason})
            continue
        try:
            res = _CHANNELS[name][1](title, text)
        except Exception as e:  # 单通道异常不影响其它通道与主流程
            res = {"channel": name, "ok": False, "error": f"{type(e).__name__}: {e}"}
        results.append(res)
        delivered = delivered or res.get("ok", False)

    local_file = None
    if always_local or not delivered:
        try:
            local_file = write_local(title, text)
        except Exception as e:  # pragma: no cover - 落地失败也不崩
            _log_warn(f"本地落地失败: {e}")

    return {"channels": results, "local_file": local_file, "delivered": delivered}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_channels(rows):
    print("=" * 56)
    print("交付通道状态")
    print("=" * 56)
    for r in rows:
        flag = "✅" if r["available"] else "⏭️ "
        print(f"  {flag} {r['channel']:<10} {r['reason']}")
    print("  📄 local      始终可用（兜底落地到 "
          f"{_notify_dir()}）")


def _print_result(res):
    for r in res["channels"]:
        if r.get("ok"):
            extra = f"（{r.get('parts', 1)} 条"
            if r.get("text_fallback"):
                extra += "，卡片→文本回退"
            extra += "）"
            print(f"  ✅ {r['channel']} 已发送 {extra}")
        elif r.get("skipped"):
            print(f"  ⏭️  {r['channel']} 跳过：{r.get('error')}")
        else:
            print(f"  ❌ {r['channel']} 失败：{r.get('error')}")
    if res["local_file"]:
        print(f"  📄 本地兜底：{res['local_file']}")
    print(f"  → delivered={res['delivered']}")


def main():
    parser = argparse.ArgumentParser(
        description="多通道交付 / 推送（Telegram + 飞书 + 本地兜底）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("channels", help="查看通道状态")

    p_send = sub.add_parser("send", help="发送一条消息")
    p_send.add_argument("--title", default="", help="标题")
    p_send.add_argument("--text", help="正文文本")
    p_send.add_argument("--file", help="从文件读取正文")
    p_send.add_argument("--channels", help="逗号分隔指定通道，如 telegram,feishu")
    p_send.add_argument("--local", action="store_true", help="无论是否远程成功都落地本地")
    p_send.add_argument("--json", action="store_true", help="输出 JSON 结果")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    ch = None
    if getattr(args, "channels", None):
        ch = [c.strip() for c in args.channels.split(",") if c.strip()]

    if args.command == "channels":
        rows = channel_status(ch)
        if "--json" in sys.argv:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_channels(rows)
        return

    # send
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    elif args.text is not None:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("❌ 需提供 --text / --file / stdin 之一", file=sys.stderr)
        sys.exit(1)

    res = notify(args.title, text, channels=ch, always_local=args.local)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_result(res)


if __name__ == "__main__":
    main()
