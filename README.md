# ReelShort Web API Docs

Reverse-engineered reference for the **ReelShort web client** (`www.reelshort.com`) — endpoints, request signing, response format, content resolution pipeline and **Arabic (`lang=ar`) localization**.

Everything below was validated live against the production web client.

> **Unofficial.** Independent reverse-engineering of publicly served client code for research and interoperability purposes. Not affiliated with, endorsed by, or produced by Crazy Maple Studio / ReelShort. Trademarks belong to their respective owners.

---

## 1. Stack & Base URL

| Item | Value |
|---|---|
| Frontend | Next.js (pages router, SSR) |
| HTTP client | axios |
| API base | `https://www.reelshort.com/api` (**same-origin**, no separate API host in the prod bundle) |
| Media CDN | `https://v-mps.crazymaplestudios.com` (video), `https://v-img.crazymaplestudios.com` (images) |
| Client version | `clientVer=2.4.00`, `apiVersion=1.0.4` |

> `API_DOMAIN` is read from `process.env.API_DOMAIN` at build time; in the shipped bundle it resolves to `""`, so all calls go to the site origin.

---

## 2. Request signing

Every API call carries these **headers** (merged into the axios request interceptor):

| Header | Example | Notes |
|---|---|---|
| `apiVersion` | `1.0.4` | overridable per request |
| `channelId` | `WEB41001` | desktop · `WEB42001` mobile · `TEST41001`/`TEST42001` non-prod |
| `clientVer` | `2.4.00` | |
| `devId` | `aXk9Qm2Lp0Zt1791145000000` | 12 random chars + epoch ms, persisted in `localStorage` |
| `lang` | `en` / `ar` | **drives catalog localization** (see §6) |
| `session` | `""` (anon) | server-side session token |
| `ts` | `1791145221` | unix seconds |
| `uid` | `0` (anon) | |
| `sign` | `9f3c…` | HMAC-SHA256, see below |

### Algorithm

```
1. payload = request_body ∪ common_headers
2. drop entries where value is "", null, undefined or the string "null"
3. JSON.stringify any object/array values
4. sort keys ascending (byte order)
5. canonical = "k=v&k=v&…"
6. sign = HMAC_SHA256(canonical, SECRET)   → lowercase hex
```

```python
SECRET = "zj8N6zKEdrK8d1MxwHSvExdgQ868q1yT"   # bundle: _app-*.js → module 75602 → fn R
```

> The secret ships inside the public JS bundle, so it is not a server-side secret. It only authenticates *client shape*, not *user entitlement*.

### Minimal working request

```bash
curl -s 'https://www.reelshort.com/api/video/book/getChapterInfo?book_id=…&chapter_id=…' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0' \
  -H 'apiVersion: 1.0.4' -H 'channelId: WEB41001' -H 'clientVer: 2.4.00' \
  -H 'devId: aXk9Qm2Lp0Zt' -H 'lang: en' -H 'ts: 1791145221' -H 'uid: 0' -H 'session: ' \
  -H 'sign: <hmac>'
```

---

## 3. Response format

### Plain JSON (majority)

```json
{ "code": 0, "msg": "success", "server_time": 1791145221, "data": { … } }
```

| `code` | Meaning |
|---|---|
| `0` | success |
| `101` | **login / session required** (client redirects to `/login`) |
| `104` | validation error — `data` lists offending fields |
| `403` | forbidden |
| `405` | wrong HTTP method |
| `100002` | missing required field |

### Encrypted body (some responses)

When the body is an opaque `base64` string instead of JSON, the client decrypts it:

```
AES-128-CBC (PKCS7)
  key = "VvRSNGFynLBW7aCP"
  iv  = "gLn8sxqpzyNjehDP"
→ base64 decode
→ zlib inflate
→ JSON
```

(CryptoJS exposes the plaintext as `WordArray.toString(Base64)`, which is why the JS
source appears to `base64decode` twice — from Python it is a single decode.)

Implemented in `_app-*.js` module `75602` (`fn N` / export `a8`), invoked by the axios **response** interceptor when the body is a non-JSON string.

### Second AES pair (different helper)

```
key = "jlcVUHH9XgmYlfsK"
iv  = "fOEZ9V4a3VaniWAa"
```

---

## 4. API reference

### Content / catalog (no session required)

| Method | Path | Params | Purpose |
|---|---|---|---|
| POST | `/api/ms/hall/webInfo` | body `{}` | Home feed: banners, tabs, lists, `chapter_count`, `play_info` |
| POST | `/api/ms/hall/webBookShelfPage` | body `{}` | Bookshelf page |
| GET | `/api/video/book/getBookInfo` | `?book_id=` | Series detail + `online_base[]` (full chapter index) |
| GET | `/api/video/book/getChapterInfo` | `?book_id=&chapter_id=` | **Episode metadata incl. `video_url` (m3u8)** |
| GET | `/api/video/book/getFreeChapter` | `?book_id=&chapter_id=` | Free-episode payload |
| GET | `/api/video/book/getTagList` | `?language=` | Tag taxonomy (**localized names**) |
| GET | `/api/video/book/getTagBook` | `?tag_id=&language=&page=&page_size=` | Books for a tag |
| POST | `/api/video/search/webSearch` | `{ word, page }` | Search |
| POST | `/api/video/search/searchByNewTag` | `{ word, page }` | Tag search |
| POST | `/api/video/book/getNewTagBook` | `{ … }` | New-tag listing |
| POST | `/api/ms/hall/webNewReleaseBooks` | `{ book_id, … }` | New releases |

### Session-gated (`code: 101` when `session` is empty)

| Method | Path | Body |
|---|---|---|
| POST | `/api/video/book/getChapterList` | `{ book_id }` |
| POST | `/api/video/book/getChapterContent` | `{ book_id, chapter_id, … }` |
| POST | `/api/video/book/getRecommendBook` | `{ book_id, … }` |
| POST | `/api/video/book/myHistory` | `{ page }` |
| POST | `/api/video/book/getMyCollectList` | `{ page }` |
| POST | `/api/video/book/addBookCollect` / `delBookCollect` | `{ book_id }` |
| POST | `/api/video/book/heartBeat` | playback heartbeat |
| POST | `/api/video/user/getUserInfo` | `{ target_uid }` |
| POST | `/api/video/user/accountLogs` | `{ … }` |

### Auth / account

| Method | Path | Notes |
|---|---|---|
| POST | `/api/video/user/userLogin` | body gets `dev_model: "h5"` appended |
| POST | `/api/video/user/thirdLoginCheck` | Google / Facebook / Apple / TikTok |
| POST | `/api/video/user/sendEmailCode` · `checkEmailCode` · `changeEmailPassword` | |
| POST | `/api/video/user/sendSmsCode` · `checkPhone` · `phoneBind` | |
| POST | `/api/auth/innerH5login` | in-app H5 login |

### Publishing (creator / contest)

| Method | Path |
|---|---|
| GET/POST | `/api/ms/contest/v1/story/detail/`, `/story/save/`, `/user/stories/overview` |
| POST | `/api/ms/contest/v1/chapter/save`, `/chapter/move/` |
| POST | `/api/ms/contest/v1/sts_token` |

### Observability headers seen on responses

`X-Request-ID`, `X-B3-TraceId` / `X-B3-SpanId` / `X-B3-ParentSpanId` / `X-B3-Sampled`, `EagleEye-TraceID` / `EagleEye-SessionID` / `EagleEye-pAppName`, `uber-trace-id`.

---

## 5. Content resolution pipeline

```
/movie/<slug>-<book_id>
   └─ __NEXT_DATA__.props.pageProps.data.online_base[]   ← all chapter_id + serial_number (public)

GET /api/video/book/getChapterInfo?book_id=&chapter_id=
   └─ data.video_url                                     ← HLS m3u8

GET <video_url>
   └─ #EXTINF × N  →  <base>-00001.ts …                  ← segments
```

Full working example: [`examples/client.py`](examples/client.py).

### SSR shortcut

The episode route embeds the same payload server-side:

```
GET /episodes/episode-<n>-<slug>-<book_id>-<chapter_id>?play_time=1
→ __NEXT_DATA__.props.pageProps.data.video_url
```

---

## 6. Arabic localization (`lang=ar`)

### 6.1 UI locale

| Route | Status |
|---|---|
| `/ar` | ✅ `locale=ar`, `<html lang="ar">` |
| `/ar/search` | ✅ |
| `/ar/login` | ✅ |
| `/ar/fandom/` | ✅ (301 → trailing slash) |
| `/ar/movie/[slug]` | ⚠️ **301 → non-localized path** |
| `/ar/episodes/[slug]` | ⚠️ **301 → non-localized path** |

i18n is `next-i18next`; `__NEXT_DATA__.props.pageProps.__namespaces` exposes `common`, `home`, `search`, `movie`.

### 6.2 API-level language

Set the **`lang` request header** (it participates in the signature):

```bash
-H 'lang: ar'
```

| Endpoint | `lang=en` | `lang=ar` |
|---|---|---|
| `POST /api/ms/hall/webInfo` | 129 titles, 0 Arabic | **104 titles, 104 Arabic** |
| `POST /api/video/search/webSearch` | English titles | Arabic titles |
| `GET /api/video/book/getTagList?language=ar` | — | **127 / 142 Arabic names** |
| `GET /api/video/book/getBookInfo` | English | ⚠️ still English, `book_sub_title: []` |
| `GET /api/video/book/getChapterInfo` | English | ⚠️ `lang` stays `en` |

> **Coverage gap:** 25 of 129 books have no Arabic title and are silently dropped from the `ar` home feed. `special_desc` (synopsis) is never localized.

### 6.3 Tag language (query param, independent of header)

```http
GET /api/video/book/getTagList?language=ar   → 142 tags, 127 Arabic names
GET /api/video/book/getTagList?language=fr   → 196 tags, French names
GET /api/video/book/getTagList?language=en   → 216 tags ⚠️ currently returns HTTP 500
```

### 6.4 Media tracks

The m3u8 returned by `getChapterInfo` is a **media playlist** (not a master playlist):

- no `#EXT-X-STREAM-INF` → single rendition
- no `#EXT-X-MEDIA` / `AUDIO=` / `SUBTITLES=` → **no alternate audio, no subtitle track**
- `has_dub: false`, `MultiBit: 0`

So: **UI + titles + tags localize to Arabic; synopsis, detail metadata, audio and subtitles do not.**

---

## 7. Security notes

See [`SECURITY.md`](SECURITY.md) for the entitlement / access-control findings and their remediation.

---

## 8. Repository layout

```
reelshort-api-docs/
├── README.md              ← this file
├── SECURITY.md            ← findings + remediation
├── .gitignore
└── examples/
    ├── client.py          ← signed request helper + decryptor
    └── i18n_ar.py         ← lang=ar coverage matrix
```

```bash
cd examples
python3 client.py
python3 i18n_ar.py
```

Dependencies: `pycryptodome` (AES), stdlib for the rest.

---

## License

MIT — see `LICENSE`.
