#!/usr/bin/env python3
"""Arabic (`lang=ar`) coverage matrix.

    pip install pycryptodome
    python3 i18n_ar.py
"""

from __future__ import annotations

import re

from client import DEMO_BOOK_ID, request

ARABIC = re.compile(r"[؀-ۿ]")


def arabic_ratio(titles: list[str]) -> str:
    if not titles:
        return "0/0"
    ar = sum(1 for t in titles if ARABIC.search(str(t)))
    return f"{ar}/{len(titles)}"


def book_titles(envelope: dict) -> list[str]:
    titles: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            if "book_title" in node:
                titles.append(node["book_title"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(envelope.get("data"))
    return titles


def main() -> None:
    print("== Catalog localization (lang header) ==")
    for lang in ("en", "ar"):
        titles = book_titles(request("/api/ms/hall/webInfo", {}, lang=lang))
        sample = ", ".join(titles[:2])
        print(f"  hall/webInfo lang={lang:<3} titles={len(titles):<4} arabic={arabic_ratio(titles):<6} e.g. {sample}")

    print("\n== Search ==")
    for lang in ("en", "ar"):
        res = request("/api/video/search/webSearch", {"word": "genie", "page": 1}, lang=lang)
        names = [x.get("book_title") for x in (res.get("data") or {}).get("lists", [])[:4]]
        print(f"  webSearch lang={lang:<3} {names}")

    print("\n== Tag taxonomy (?language= query) ==")
    for language in ("ar", "fr", "de", "en"):
        res = request("/api/video/book/getTagList", query=f"?language={language}")
        data = res.get("data")
        if isinstance(data, list):
            ar = sum(1 for x in data if ARABIC.search(str(x.get("name", ""))))
            print(f"  getTagList language={language:<3} n={len(data):<4} arabic_names={ar}")
        else:
            print(f"  getTagList language={language:<3} code={res.get('code')} "
                  f"data={data!r}  <- see SEC-03")

    print("\n== Detail endpoints (currently ignore lang) ==")
    for lang in ("en", "ar"):
        book = request("/api/video/book/getBookInfo", query=f"?book_id={DEMO_BOOK_ID}", lang=lang)["data"]
        print(f"  getBookInfo lang={lang:<3} book_title={book['book_title']!r} "
              f"book_sub_title={book['book_sub_title']} special_desc_lang={lang}")

    print("\n== Media tracks ==")
    chapter = request(
        "/api/video/book/getChapterInfo",
        query=f"?book_id={DEMO_BOOK_ID}&chapter_id=1gv8oeozxn",
    )["data"]
    print(f"  has_dub={chapter['has_dub']} MultiBit={chapter['MultiBit']}")
    print(f"  video_url={chapter['video_url']}")
    print("  playlist is media-only: no #EXT-X-STREAM-INF, no AUDIO=, no SUBTITLES=")


if __name__ == "__main__":
    main()
