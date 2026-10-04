# Security Notes

Behaviour observed while reverse-engineering the web client, each with a suggested fix. Reported here for transparency — see [Reporting](#reporting).

---

## SEC-01 — Entitlement check is client-side only

| | |
|---|---|
| **Class** | Broken access control / business logic — CWE-639, CWE-862 |
| **Severity** | High |
| **Status** | Open |
| **Affected** | `GET /api/video/book/getChapterInfo` · SSR `/episodes/[slug]` · CDN `v-mps.crazymaplestudios.com` |

### Description

Premium gating is derived from `is_lock` / `vip_free` / `firstLockIndex`, which the client computes from
`POST /api/video/book/getChapterList`. That endpoint **is** correctly gated (`code: 101` without a session).

However `GET /api/video/book/getChapterInfo` returns `video_url` unconditionally for every chapter,
regardless of `serial_number` vs `paid_start`. The returned manifest is the **full-length** playlist and the
CDN serves every segment without a signed token or `Referer` check.

### Reproduction

```http
GET /api/video/book/getBookInfo?book_id=6a5191d8fa9f9f7a09081789
→ data.paid_start = 10, data.online_base[] = 51 chapters with public chapter_id

GET /api/video/book/getChapterInfo?book_id=…&chapter_id=zcmlqggbkj   # serial 51
→ code: 0, data.serial_number: 51, data.video_url: "https://v-mps…/…-sd.m3u8"

GET https://v-mps.crazymaplestudios.com/…/…-sd.m3u8
→ 18 × #EXTINF:5.000000 ≈ 90 s  (data.duration = 89)   — full episode

GET …-00017.ts → 200, 550 KB
GET …-00018.ts → 200, 115 KB
```

Reproduced on 4 titles:

| Title | `paid_start` / `total` | Last chapter leaks `video_url` |
|---|---|---|
| The Great and Powerful Genie | 10 / 51 | yes |
| In Bed with My Brother-in-Law | 16 / 45 | yes |
| The Alpha Princess Is Gone for Good | 11 / 55 | yes |
| You Can't Stop My Super X-Ray Vision | 11 / 58 | yes |

The same payload is exposed server-side in `__NEXT_DATA__` on `/episodes/[slug]`.

### Impact

Premium catalogue is retrievable without an account or entitlement. Direct revenue exposure and bulk extraction.

### Remediation

1. Enforce entitlement **inside** `getChapterInfo`: when `serial_number >= paid_start` and the caller has no
   active entitlement, return `is_lock: 1` and omit `video_url` (or return a preview-only manifest).
2. Apply the same check in the SSR layer before writing `props.pageProps.data`.
3. Sign CDN URLs (`?token=<hmac>&exp=`) and validate at the edge; reject unsigned requests.
4. Never derive lock state solely from the client (`firstLockIndex` / `vip_free`).

---

## SEC-02 — Client signing secret is public

| | |
|---|---|
| **Class** | Hardcoded credential in client — CWE-798 |
| **Severity** | Informational |
| **Status** | Accepted (by design) |

`HMAC_SHA256` key `zj8N6zKEdrK8d1MxwHSvExdgQ868q1yT` and the AES keys
`VvRSNGFynLBW7aCP` / `gLn8sxqpzyNjehDP` are embedded in `_app-*.js`.

These validate **client shape**, not identity. Documented here so nobody mistakes them for server secrets.
If stronger client attestation is wanted, move signing server-side behind a thin BFF.

---

## SEC-03 — `getTagList?language=en` returns HTTP 500

| | |
|---|---|
| **Class** | Improper input validation / error handling — CWE-755 |
| **Severity** | Low |
| **Status** | Open |

```http
GET /api/video/book/getTagList?language=en   → HTTP 500 (empty body)
GET /api/video/book/getTagList?language=ar   → HTTP 200 (142 tags)
GET /api/video/book/getTagList?language=fr   → HTTP 200 (196 tags)
GET /api/video/book/getTagList?language=zh   → HTTP 200, data: {}   ← should be []
```

Two problems: an unhandled exception escapes as a raw 500 instead of the normal envelope
(`{code, msg, data}`), and unsupported languages return an object where a list is expected.

Fallback to `en` for the tag set, return `code: 0`, and always return `data` as an array.

---

## SEC-04 — Localization gaps

| | |
|---|---|
| **Class** | Functional / consistency |
| **Severity** | Info |

- `/ar/movie/[slug]` and `/ar/episodes/[slug]` 301 to their non-localized paths.
- `getBookInfo` and `getChapterInfo` ignore the `lang` header (title / `special_desc` stay English).
- 25 of 129 catalogue entries have no Arabic title and are dropped from the `lang=ar` home feed.
- Search occasionally returns an untranslated UI string as a result title
  (e.g. `"التحقق عبر الإنترنت (en)"`).

---

## Reporting

Found something else? Open an issue here, or report it to the vendor through their official security / bug-bounty channel.
