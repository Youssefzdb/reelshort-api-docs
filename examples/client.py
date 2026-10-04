#!/usr/bin/env python3
"""Reference client for the ReelShort web API.

Signs requests (HMAC-SHA256), handles the optional encrypted response envelope
and exercises the main content endpoints.

    pip install pycryptodome
    python3 client.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import string
import time
import urllib.error
import urllib.request
import zlib
from typing import Any

BASE = "https://www.reelshort.com"

SIGN_SECRET = "zj8N6zKEdrK8d1MxwHSvExdgQ868q1yT"
AES_KEY = b"VvRSNGFynLBW7aCP"
AES_IV = b"gLn8sxqpzyNjehDP"

COMMON = {
    "apiVersion": "1.0.4",
    "channelId": "WEB41001",
    "clientVer": "2.4.00",
    "lang": "en",
    "session": "",
    "uid": "0",
}

DEMO_BOOK_ID = "6a5191d8fa9f9f7a09081789"


# ---------------------------------------------------------------- signing ---

def make_sign(payload: dict[str, Any]) -> str:
    items = []
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, separators=(",", ":"))
        if value in ("", None, "null"):
            continue
        items.append((key, str(value)))
    items.sort(key=lambda kv: kv[0])
    canonical = "&".join(f"{k}={v}" for k, v in items)
    return hmac.new(SIGN_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def dev_id() -> str:
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=12))
    return f"{rand}{int(time.time() * 1000)}"


# ----------------------------------------------------------------- transport --

def request(
    path: str,
    body: dict[str, Any] | None = None,
    *,
    method: str | None = None,
    query: str = "",
    lang: str = "en",
    session: str = "",
    uid: str = "0",
    timeout: int = 25,
) -> dict[str, Any]:
    """Call an API endpoint and return the decoded JSON envelope."""
    headers = dict(COMMON, lang=lang, session=session, uid=uid, devId=dev_id(), ts=str(int(time.time())))
    payload = dict(body or {})
    payload.update(headers)
    headers["sign"] = make_sign(payload)
    headers["Content-Type"] = "application/json"
    headers["User-Agent"] = "Mozilla/5.0"

    verb = method or ("POST" if body is not None else "GET")
    data = json.dumps(body).encode() if (body is not None and verb in ("POST", "PUT")) else None
    req = urllib.request.Request(BASE + path + query, data=data, headers=headers, method=verb)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return {"code": exc.code, "msg": "http-error", "data": exc.read().decode()[:500]}

    return decode(raw)


# ---------------------------------------------------------------- decryption --

def decode(raw: str) -> dict[str, Any]:
    """Plain JSON, or the AES + double-base64 + deflate envelope."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    from Crypto.Cipher import AES  # pycryptodome

    plain = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(base64.b64decode(raw))
    inflated = zlib.decompress(base64.b64decode(plain))
    return json.loads(inflated)


# ---------------------------------------------------------------------- demo --

def show(label: str, envelope: dict[str, Any], *fields: str) -> None:
    data = envelope.get("data")
    extra = ""
    if isinstance(data, dict) and fields:
        extra = " | " + " ".join(f"{f}={data.get(f)}" for f in fields)
    print(f"{label:<34} code={envelope.get('code')}{extra}")


def main() -> None:
    show("webInfo (POST)", request("/api/ms/hall/webInfo", {}))

    book = request("/api/video/book/getBookInfo", query=f"?book_id={DEMO_BOOK_ID}")["data"]
    print(f"{'getBookInfo (GET)':<34} book_title={book['book_title']} "
          f"paid_start={book['paid_start']} total={book['total']}")

    chapters = book["online_base"]
    print(f"  chapters indexed: {len(chapters)} "
          f"(first={chapters[0]['chapter_id']}, last={chapters[-1]['chapter_id']})")

    last = chapters[-1]
    ep = request("/api/video/book/getChapterInfo",
                 query=f"?book_id={DEMO_BOOK_ID}&chapter_id={last['chapter_id']}")["data"]
    show("getChapterInfo (GET)", {"code": 0}, "serial_number", "duration")
    print(f"  video_url = {ep['video_url']}")

    show("webSearch (POST)", request("/api/video/search/webSearch", {"word": "genie", "page": 1}))
    show("getChapterList (session)", request("/api/video/book/getChapterList", {"book_id": DEMO_BOOK_ID}))
    show("getTagList (GET)", request("/api/video/book/getTagList", query="?language=ar"))


if __name__ == "__main__":
    main()
