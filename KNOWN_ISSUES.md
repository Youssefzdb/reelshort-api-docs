# Known issues

Behaviour notes and edge cases found while writing this documentation, each with a suggested fix.

---

## Issue 01 — `getChapterInfo` does not check entitlement

| | |
|---|---|
| **Affects** | `GET /api/video/book/getChapterInfo` · SSR `/episodes/[slug]` · CDN `v-mps.crazymaplestudios.com` |
| **Status** | Open |

### Description

Lock state (`is_lock`, `vip_free`, `firstLockIndex`) is computed by the client from
`POST /api/video/book/getChapterList`, which is correctly gated (`code: 101` without a `session`).

`GET /api/video/book/getChapterInfo`, however, returns `video_url` for every chapter regardless of
`serial_number` vs `paid_start`, so callers without an active entitlement receive the same payload as
entitled users. The returned manifest is the full-length playlist, and the CDN serves segments without a
signed token or `Referer` check.

### Observed

```http
GET /api/video/book/getBookInfo?book_id=6a5191d8fa9f9f7a09081789
→ data.paid_start = 10, data.online_base[] = 51 chapters with public chapter_id

GET /api/video/book/getChapterInfo?book_id=…&chapter_id=zcmlqggbkj   # serial 51
→ code: 0, data.serial_number: 51, data.video_url: "https://v-mps…/…-sd.m3u8"

GET https://v-mps.crazymaplestudios.com/…/…-sd.m3u8
→ 18 × #EXTINF:5.000000 ≈ 90 s  (data.duration = 89)

GET …-00017.ts → 200, 550 KB
GET …-00018.ts → 200, 115 KB
```

Observed on 4 titles:

| Title | `paid_start` / `total` | `video_url` returned for last chapter |
|---|---|---|
| The Great and Powerful Genie | 10 / 51 | yes |
| In Bed with My Brother-in-Law | 16 / 45 | yes |
| The Alpha Princess Is Gone for Good | 11 / 55 | yes |
| You Can't Stop My Super X-Ray Vision | 11 / 58 | yes |

The same payload is present server-side in `__NEXT_DATA__` on `/episodes/[slug]`.

### Suggested fix

1. Enforce entitlement inside `getChapterInfo`: when `serial_number >= paid_start` and the caller has no
   active entitlement, return `is_lock: 1` and omit `video_url` (or return a preview-only manifest).
2. Apply the same check in the SSR layer before writing `props.pageProps.data`.
3. Sign CDN URLs (`?token=<hmac>&exp=`) and validate at the edge; reject unsigned requests.
4. Don't derive lock state solely on the client (`firstLockIndex` / `vip_free`).

---

## Issue 02 — Signing keys ship in the public bundle

| | |
|---|---|
| **Affects** | `_app-*.js` |
| **Status** | Accepted (by design) |

The `HMAC_SHA256` key `zj8N6zKEdrK8d1MxwHSvExdgQ868q1yT` and the AES keys
`VvRSNGFynLBW7aCP` / `gLn8sxqpzyNjehDP` are embedded in the shipped bundle.

They validate **client shape**, not identity — documented here so they aren't mistaken for server secrets.
If stronger client attestation is required, move signing behind a thin server-side BFF.

---

## Issue 03 — `getTagList?language=en` returns HTTP 500

| | |
|---|---|
| **Affects** | `GET /api/video/book/getTagList` |
| **Status** | Open |

```http
GET /api/video/book/getTagList?language=en   → HTTP 500 (empty body)
GET /api/video/book/getTagList?language=ar   → HTTP 200 (142 tags)
GET /api/video/book/getTagList?language=fr   → HTTP 200 (196 tags)
GET /api/video/book/getTagList?language=zh   → HTTP 200, data: {}   ← expected []
```

Two problems: an unhandled exception escapes as a raw 500 instead of the normal envelope
(`{code, msg, data}`), and unsupported languages return an object where a list is expected.

Fallback to `en` for the tag set, return `code: 0`, and always return `data` as an array.

---

## Issue 04 — Localization gaps

| | |
|---|---|
| **Affects** | `/ar/*` routes · `getBookInfo` · `getChapterInfo` · home feed |
| **Status** | Open |

- `/ar/movie/[slug]` and `/ar/episodes/[slug]` 301 to their non-localized paths.
- `getBookInfo` and `getChapterInfo` ignore the `lang` header (title / `special_desc` stay English).
- 25 of 129 catalogue entries have no Arabic title and are dropped from the `lang=ar` home feed.
- Search occasionally returns an untranslated UI string as a result title
  (e.g. `"التحقق عبر الإنترنت (en)"`).

---

## Contributing

Spotted something else? Open an issue, or use the channel in [`SECURITY.md`](SECURITY.md).
