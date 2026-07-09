# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (always first)
source venv/bin/activate

# Run local server
APP_ENV=local uvicorn main:app --reload

# Run production server
APP_ENV=production uvicorn main:app
```

## Environment

`APP_ENV` selects the env file (`app/core/config.py`): if `APP_ENV` is set, loads `.env.<APP_ENV>`; if unset/empty, falls back to `.env`.
- `.env` — fallback when `APP_ENV` is not set (e.g. plain `uvicorn main:app`)
- `.env.local` — local development (`APP_ENV=local`)
- `.env.production` — production (`APP_ENV=production`)

**Never commit env files.** `.env`, `.env.local`, and `.env.production` are all gitignored — they hold secrets (`SECRET_KEY`, DB credentials, `LMS_API_KEY`). Only `.env.example` (no real values) is tracked. If a secret is ever committed, purge it from history and rotate the value, not just `git rm`.

`Settings` in `app/core/config.py` has no Python defaults (except `LMS_API_KEY = ""`) — all other values must come from the env file. When adding a new setting, add it to every env file in use.

Required env vars: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `QR_CODE_VALIDITY_MINUTES`.

**DATABASE_URL must include `?charset=utf8mb4`** to prevent Korean/CJK text corruption (e.g. `mysql+pymysql://...?charset=utf8mb4`).

Optional env vars: `LMS_API_KEY` — shared secret for LMS → Staff API notification calls. Defaults to empty (API key auth disabled). The env var `LMS_API_KEY` (server side) and the request header `X-API-Key` (caller side) are the same secret under two names: `require_admin_or_api_key` compares the incoming `X-API-Key` header against `settings.LMS_API_KEY` via `secrets.compare_digest`. Behavior in `app/core/dependencies.py`: if the request sends an `X-API-Key` header but `LMS_API_KEY` is empty → `500 "LMS_API_KEY not configured"`; if it doesn't match → `403`. When testing `/notifications/send` as an admin, send only the `Bearer` JWT and **omit** the `X-API-Key` header (sending it forces the API-key path).

## Architecture

**Layer structure:**
```
controllers/ → services/ → models/
     ↓              ↓
  schemas/       database.py (get_db)
```

- `controllers/` — FastAPI routers. HTTP request/response only, no business logic
- `services/` — Business logic. All DB operations happen here
- `models/` — SQLAlchemy ORM models
- `schemas/` — Pydantic request/response schemas
- `core/` — Config, DB session, auth dependencies, security utils, constants
- `utils/` — Expo push notification helper

All routers are registered in `app/core/router.py` under `/api/v1/<path>`.

**DB transaction rules:**
`get_db` automatically commits on success and rolls back on exception. Services never call `db.commit()` directly. Use `await db.flush()` only when you need DB-generated values (e.g. `id`) immediately after an insert.

**Auth flow:**
- `Bearer` JWT access token (short-lived, `ACCESS_TOKEN_EXPIRE_MINUTES`)
- Opaque refresh token — only the SHA-256 hash is stored in DB; the raw token is returned to the client
- Inject `get_current_user` / `require_manager` / `require_admin` from `app/core/dependencies.py` via `Depends`

**Role permissions:**
| Action | staff | manager | admin |
|--|:--:|:--:|:--:|
| View notices / announcements / schedule / bulletin / weekly vision | O | O | O |
| Send push notifications | X | X | O (or LMS API Key) |

**This API is read-only for content.** Schedules, announcements, bulletin/notice posts, and weekly vision are created/edited/deleted **directly in the DB by the LMS** — the Staff API's write routes (`POST/PUT/DELETE` on `/schedule`, `/announcements`, `/bulletin`) were **removed**; only `GET` remains. The one content-mutating endpoint is `POST /notifications/send` (admin JWT or LMS `X-API-Key`). Per-user self-service writes remain: `PATCH /users/me` (profile) and `POST /users/me/password`.

Announcement `target_role` visibility: staff sees `all/staff`, manager/admin see `all/staff/manager` (`announcement_service._VISIBLE_ROLES`). This visibility (plus the publish/expire window) is enforced on **both** the list and the single `GET /announcements/{id}` fetch, so a lower role can't read a higher-targeted (or unpublished/expired) announcement by iterating ids.

## Attendance QR Flow

The employee app generates the QR client-side; an external scanner reads it. The server auto-determines checkin vs checkout based on today's existing record.

1. Frontend: constructs a static token `e{user.id}` (not a JWT) from the authenticated user's ID and renders it as a QR image client-side
2. Frontend: polls `GET /api/v1/attendance/qr/status` (auth required via Bearer token) every ~2s to check scan status
3. Scanner: `POST /api/v1/attendance/scan` `{ token, ip, device }` — parses `e{user.id}` format, auto-determines checkin/checkout, records attendance; no auth required
4. Poll response `status`: `pending` → `checked_in` / `checked_out` (stop polling); `expired` is a client-side concept only

`QR_CODE_VALIDITY_MINUTES` is defined in config but not currently enforced server-side — expiry is managed by the frontend.

Kiosk alternative: `POST /api/v1/attendance/manual` `{ wid, ip, device }` — bypasses QR, uses `t_user.id` directly. Same checkin/checkout logic applies.

`t_usertimecheck` is **one row per day** (checkin and checkout on the same row). Server logic: no record today → checkin; checkin but no checkout → checkout; both exist → 409 error.

"Today" is determined using Eastern Time (`APP_TZ` in `app/core/constants.py`). All `today_start` calculations use ET midnight converted to UTC before querying the DB.

## Push Notifications (Expo)

Push uses the Expo Push API over HTTP (`httpx`). Code: `app/utils/expo_push.py` (Expo wrapper), `app/services/notification_service.py`, `app/controllers/notifications.py`, models in `app/models/notification.py`.

**Endpoints** (under `/api/v1/notifications`):
- `POST /token` — register/refresh the caller's Expo push token (auth: `get_current_user`). Upsert keyed on `(user_id, device_id)`; re-registering reactivates and updates the token.
- `DELETE /token?device_id=...` — deactivate the caller's token for that device (sets `is_active = False`; not a hard delete).
- `POST /send` — send a notification (auth: `require_admin_or_api_key` — admin JWT or `X-API-Key` header). `user_ids` list → target those users; `user_ids` omitted/null → broadcast to all. Creates `t_notification_recipient` records for read/unread tracking.
- `GET ` (no trailing slash) — paginated notification list for current user (auth: `get_current_user`). Returns `items`, `total`, `unread_count`. Route is registered as `@router.get("")` (not `"/"`) so it responds at `/api/v1/notifications` without a 307 trailing-slash redirect — mobile clients drop the auth header/query on redirect. All list routes in this codebase use `""`, not `"/"`.
- `GET /unread-count` — unread notification count for current user.
- `PATCH /{recipient_id}/read` — mark a single notification as read.
- `PATCH /read-all` — mark all notifications as read for current user.

**Tables** (`t_push_token`, `t_notification_log`, `t_notification_recipient`) — created via `changelog.sql`. `t_push_token` has a unique key on `(user_id, device_id)`. `t_notification_recipient` has a unique key on `(notification_id, user_id)` and tracks `is_read`/`read_at` per user. `user_id` is `int` (FK → `t_user.id`); the row PK `id` is `bigint`. The token column is `push_token`; the log column is `push_response`.

**Send flow** — two phases so the DB connection is never held during the external Expo HTTP call:
- `notification_service.prepare_notification` (runs in the request transaction, via `get_db`): writes a `t_notification_log` row with `status="pending"` (`db.flush()` to get `log.id`), then creates `t_notification_recipient` rows for each target user. The controller (`POST /send`) then schedules `dispatch_notification` via FastAPI `BackgroundTasks` and returns immediately. The request transaction commits (log + recipients) **before** the background task runs.
- `notification_service.dispatch_notification` (runs after the response, in its **own** short-lived sessions from `AsyncSessionLocal` — must `commit()` explicitly since there's no `get_db`): reads active tokens (session closed before the HTTP call), sends push while holding **no** DB connection, then reopens a session to update `log.status`/`push_response`/`sent_at` and deactivate dead tokens. This is the fix for the old design that held a pooled connection open across the multi-second Expo call.
- The `t_notification_log` row stores the **original HTML** `title`/`body` (used for in-app notification modal rendering). Before sending to Expo, both are run through `_strip_html()` (stdlib `re` + `html.unescape`) so OS push banners show clean plain text — tags removed, entities decoded, whitespace collapsed. DB keeps HTML; the banner gets plain text.
- Target `user_ids` are filtered to IDs that actually exist in `t_user` **and are not soft-deleted (`del_yn='N'`)** (`SELECT id ... WHERE id IN (...) AND del_yn='N'`), which also de-duplicates — preventing FK violations from bad LMS input and `(notification_id, user_id)` unique-constraint rollbacks. `user_ids = null` broadcasts to all active (non-deleted) users; `user_ids = []` (empty list) targets **nobody** — it is **not** treated as a broadcast (the code checks `is not None`, not truthiness). The broadcast token query in `dispatch_notification` joins `t_user` and excludes `del_yn='Y'`, so terminated employees' devices don't receive internal notices.
- Final `status` starts `pending` and is updated by the background task: `sent` if Expo reports ≥1 success, else `failed`; `push_response` records `success=N failure=M`. `dispatch_notification` wraps its whole body in a top-level `try/except` that best-effort marks the log `failed` (in a fresh session) on any DB error, so a DB failure during dispatch no longer silently strands the row at `pending`. Only a process death before/at dispatch can still leave a row `pending`.
- `send_push_notifications` is a blocking call — offloaded via `anyio.to_thread.run_sync` so it doesn't block the event loop.
- Batched to Expo's **100-message-per-request** limit.
- Tokens Expo reports as `DeviceNotRegistered` are auto-deactivated (`is_active = False`) so dead tokens stop accumulating.

**LMS Integration:**
- LMS calls `POST /notifications/send` with `X-API-Key` header (value must match `LMS_API_KEY` env var).
- Body: `{ "title": "...", "body": "...", "user_ids": [1, 2, 3], "data": {"route": "..."} }`.
- `user_ids` null → broadcast to all. LMS resolves group/branch membership to user IDs on its side.
- Scheduled sends are handled by LMS scheduler — Staff API sends immediately on each call.

**Runtime requirements (production):**
- No extra pip installs — `httpx` and `anyio` are already pinned in `requirements.txt`. No service-account file or credentials are required (Expo's public push endpoint).

## Notice Board (Notice)

Read-only "Notice" feature over `t_noticeboard` — the **same table** the "bulletin" CRUD writes to. Code: `app/services/notice_service.py`, `app/controllers/notice.py`, `app/models/branch.py` (`t_branch`), `app/schemas/notice.py`. Mirrors the DB stored procedures `usp_selnoticeboard` / `usp_selnoticedetail` (referenced, not called — logic is replicated in the service).

**Endpoints** (under `/api/v1/notices`, auth: `get_current_user`):
- `GET ` (no trailing slash) — paginated list; each item: `id`, `regdate` (`YYYY-MM-DD` string), `branch` (label), `title`.
- `GET /{notice_id}` — detail: adds `details` (HTML) and `noticed_by` (author `loginid`, uppercased).

**Branch visibility:** a user sees only notices where `bid = '%'` (ALL) **or** `bid = <their branch>` (`t_user.bid`). Cross-branch notices are hidden from the list and return 404 when fetched by id (IDOR-safe). To instead show every branch's notices to everyone, drop the `bid` filter in `notice_service._allowed_bids`.

**t_noticeboard semantics:**
- `bid` is a **string**: `'%'` = ALL, else a branch id (e.g. `'4'`). Branch label = `'ALL'` for `'%'`, else `t_branch.fullname` (join `t_branch.bid`, an int — MySQL implicit-casts the string).
- `wid` stores **`t_user.id`** (author), despite the name — "noticed by" is that user's `loginid`. Writes are owned by the LMS (see below), which must set `wid = t_user.id` for the author to resolve.
- `title`/`details` may be HTML with inline links and large base64 images — the app renders `details` via `RenderHtml` (safe link/tag props). Some rows are multi-MB.

## Rate Limiting

App-level, in-memory sliding-window limiter (`app/core/rate_limit.py`) applied via `Depends(rate_limit(limit, window, scope))` — login/refresh (brute force) and the unauthenticated attendance scan (flooding). Per-process (fine for the single-process deployment; limits become per-worker if scaled).

**Deployment note:** the API runs behind **Apache2** (`mod_proxy_http`) on Ubuntu (managed by systemd). Apache appends the real client IP to the **end** of `X-Forwarded-For`, so `_client_ip()` reads the **rightmost** value. Using the first value would let a client spoof `X-Forwarded-For` to get a fresh bucket per request and bypass every limit.

## DB Notes

Alembic is not used — models are written to match existing DB tables directly.

The app runtime uses `settings.ASYNC_DATABASE_URL` (aiomysql). The `ASYNC_DATABASE_URL` property in `config.py` auto-converts `DATABASE_URL` from pymysql → aiomysql.

`t_user.id` is stored in the JWT `sub` claim. **`t_usertimecheck.wid` stores `t_user.id`** (the PK, not the employee number). `t_user.bid` is the branch/location ID. Note: the notice **read** path (`usp_selnoticeboard`/`usp_selnoticedetail`, `notice_service`) treats `t_noticeboard.wid` as `t_user.id` (author). Since the Staff API no longer writes notices (the LMS writes them directly to the DB), the LMS must set `wid = t_user.id` for "noticed by" to resolve correctly.

**`wid` naming trap:** `wid` means different things per table. `t_usertimecheck.wid` = `t_user.id` (subject). `t_noticeboard.wid` = `t_user.id` (author). `t_schedule.wid` = **writer** `t_user.id` (who entered the row — NOT the schedule's subject; the subject is `tid` → `t_teacher.tid`, linked from `t_user.tid`). `t_user.wid` itself appears to be the creator's `t_user.id` (registrar), not an employee number — many accounts share the same value.

**Schedule (`t_schedule`):** the subject is `tid` (`t_teacher.tid`); users link via `t_user.tid` (nullable — staff without a teacher row have no schedules; `schedule_service` short-circuits `tid=None` to `[]`). Events can span dates (`sdate`~`edate`, `edate` may be NULL for single-day); range queries must use overlap logic (`sdate <= to AND COALESCE(edate, sdate) >= from`), not `sdate BETWEEN`. `eventtype` values seen: `class`, `tutor`, `dayoff`, `other`. Dayoffs can be partial-day (`stime`/`etime` set, `allday='N'`).

**Holidays (`t_datelist`):** date-dimension table, one row per calendar date (PK `sdate`, range 2014–2030), columns `weekday`, `holidayyn` CHAR(1), `holidaynm`, `bid` (added in `changelog.sql` 2026-07-09). `bid` is a JSON-array **string** in the same format as `t_invoiceitem.bid` (e.g. `'["6","7","4"]'`, values are stringified `t_branch.bid`): `NULL` = holiday for **all** branches (national holidays), array = only those branches (e.g. branch founding day). Branch match uses `bid LIKE '%"<bid>"%'` — the quotes prevent `"2"` from matching `"12"`; don't use `JSON_CONTAINS` (a malformed row would raise). Because PK is `sdate` and every date row already exists, LMS updates must use `INSERT ... ON DUPLICATE KEY UPDATE` — `INSERT IGNORE` silently skips existing dates. One row per date ⇒ a date can carry only **one** holiday name/bid set (a global and a branch holiday can't coexist on the same date). Holiday flags are maintained per-year by the LMS (US federal holidays); verify the current year is populated before relying on it.

**Soft deletes:** legacy tables use a `del_yn` / `delyn` CHAR(1) column (`'N'` = active, `'Y'` = deleted). Services must filter `del_yn = 'N'` on reads. Newer tables (e.g. `t_weekly_vision`) use `is_hidden` instead.

Passwords are stored using MySQL `PASSWORD()` format (`*` + uppercase SHA1(SHA1(plain))). `verify_password` in `security.py` replicates this — passlib/bcrypt is not used.

## Tests

No test suite exists yet. `tests/` contains only `__init__.py`.

## Constants

`app/core/constants.py` holds app-wide constants. Currently:
- `APP_TZ` — `ZoneInfo("America/New_York")` (Eastern Time, covers NY and GA locations)
