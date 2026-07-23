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

Required env vars: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` (2026-07-22부터 4320 = 3일; 리프레시 토큰 제거로 액세스 토큰만 사용).

**DATABASE_URL must include `?charset=utf8mb4`** to prevent Korean/CJK text corruption (e.g. `mysql+pymysql://...?charset=utf8mb4`).

Optional env vars: `LMS_API_KEY` — shared secret for LMS → Staff API notification calls. Defaults to empty (API key auth disabled). The env var `LMS_API_KEY` (server side) and the request header `X-API-Key` (caller side) are the same secret under two names: `require_admin_or_api_key` compares the incoming `X-API-Key` header against `settings.LMS_API_KEY` via `secrets.compare_digest`. Behavior in `app/core/dependencies.py`: if the request sends an `X-API-Key` header but `LMS_API_KEY` is empty → `500 "LMS_API_KEY not configured"`; if it doesn't match → `403`. When testing `/notifications/send` as an admin, send only the `Bearer` JWT and **omit** the `X-API-Key` header (sending it forces the API-key path).

**`SECRET_KEY` must be ≥32 chars and not a placeholder** — `config.py` has a `field_validator` that refuses to boot on a short/placeholder key (a weak HS256 signing key makes access tokens forgeable). `.env.example` ships an intentionally-invalid short placeholder; real env files must override it.

## Security posture (audited 2026-07-06 / 2026-07-09 / 2026-07-23 — read before "fixing" these)

This codebase was security-audited three times (2026-07-06, 2026-07-09, and a 2026-07-23 pre-release audit of the v1.2.0 refresh-token-removal release — no injection/IDOR/auth/connection findings). The items below are **known and intentional** — do not re-report or "harden" them without a product decision, or you'll re-break working behavior:

- **Unauthenticated `/attendance/scan` + `/manual`** — intentional (external scanner/kiosk can't hold a JWT). Buddy-punching is an accepted trade-off. See the Attendance QR Flow section. Mitigations in place: per-IP rate limit + active-user validation.
- **App biometric login stores the plaintext password in SecureStore** — **accepted by the product owner** (2026-07-09). The password is only ever the plaintext credential the user types anyway; biometric is a convenience auto-fill, not a second factor. `requireAuthentication: true` is intentionally NOT used (breaks many Android face-unlock / Class 1-2 sensors — see app CLAUDE.md). Do not re-flag.
- **No rate limit on authenticated GET endpoints** — intentional. They require a valid JWT and return only the caller's own branch/user-scoped data, and the home screen fires several in parallel; a limiter there would break normal use. Rate limiting is applied only where it matters: login (brute force) and the unauthenticated scan (flooding).
- **No TLS certificate pinning in the app** — accepted. Transport is HTTPS; pinning adds rotation/outage risk disproportionate to this app's threat model.
- **Git history secret leak (1st audit)** — resolved 2026-07-09: history fully purged (repo re-init, remote deleted + recreated), credentials rotated by the owner.

Accepted/deferred from the 2026-07-23 pre-release audit (also do not re-report):

- **App-side: 401-driven logout cannot deauthorize its push token** — the interceptor deletes the access token before `logout()` runs, so the `DELETE /notifications/token` call gets 403 and is skipped. Accepted: the token was already invalid, Expo `DeviceNotRegistered` auto-deactivation self-heals, and re-login upserts the same `(user_id, device_id)` row.
- **Concurrent-scan race can create a duplicate checkin row** — read-then-write with no row lock. Accepted for the single-kiosk deployment; LMS can correct rows.
- **`python-jose` is unmaintained** — its known CVEs (JWE bomb, asymmetric alg confusion) don't apply to this HS256-pinned symmetric usage. Deferred: migrate to PyJWT at the next convenient window.
- ~~`GET /attendance/history` tz 경계 오차~~ — ET 벽시계 규약 확정(2026-07-23)과 함께 tz-aware 경계를 ET naive로 정규화하는 코드가 들어가 해결됨.
- **`GET /daily-log` INNER joins task/category** — orphaned logs silently disappear. Pre-existing pending item (INNER→LEFT), not security.
- **ET-midnight open-row limitation** — documented in the Attendance QR Flow section (owner confirmed no overnight shifts).

**Datetime storage contract (2026-07-23 실측 정정 — 테이블마다 다름!):**
- **`t_usertimecheck` (출퇴근)**: LMS/터미널이 **ET 벽시계 naive**로 저장 (프로덕션 실데이터로 확인 — 아침 출근이 08:0x로 저장됨). staff-api의 `/scan`·`/manual`도 `datetime.now(APP_TZ).replace(tzinfo=None)`로 동일하게 쓰고, 조회 경계(`today_start_et`, 캘린더 월 경계)도 ET naive로 비교한다. **UTC로 "고치지" 말 것** — LMS와 어긋나며 앱 표시도 4시간 깨진다 (한 번 겪음).
- **`t_notification_*` (staff-api가 쓰는 테이블)**: naive **UTC** 저장 — 앱은 `serverTime()`으로 로컬 변환해 표시.
- 직렬화는 둘 다 오프셋 없는 ISO 문자열 (`2026-07-22T18:53:18`, no `Z`) — 어느 규약인지는 테이블(쓰는 주체)로 판단.

Genuine bugs found in the audits WERE fixed (see git log): cross-branch IDOR via `/bulletin` (endpoints removed), announcement get-by-id IDOR, XFF rate-limit bypass, production `/docs` exposure, `SECRET_KEY` strength gate, scan junk-row injection, several notification-dispatch reliability issues. If a NEW finding appears that isn't in this list or the git log, it's worth acting on.

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

**Auth flow (2026-07-22 리프레시 토큰 제거):**
- `Bearer` JWT access token only — `ACCESS_TOKEN_EXPIRE_MINUTES=4320` (3일). `/auth/login`이 유일한 auth 엔드포인트.
- Refresh token은 **제거됨** (`/auth/refresh`·`/auth/logout`·`/auth/logout-all` 삭제, `t_refresh_tokens` 테이블 드롭 대상 — changelog.sql 참조). 앱은 토큰 만료 시 재로그인(바이오메트릭 자동 입력)한다. **Accepted trade-off:** 3일 토큰은 서버측 폐기 수단이 없음(로그아웃 = 클라이언트 로컬 삭제). 단 `get_current_user`가 요청마다 `del_yn='N'`을 확인하므로 퇴사 처리된 계정의 토큰은 즉시 무효화된다.
- Inject `get_current_user` / `require_manager` / `require_admin` from `app/core/dependencies.py` via `Depends`
- **관측된 동작**: Authorization 헤더가 아예 없는 요청도 `401 "Not authenticated"`을 받는다 (403 아님). 앱 인터셉터는 이를 전제로 **"토큰을 실어 보낸 요청의 401"만** 세션 만료로 처리한다 — 헤더 없는 401을 로그아웃 사유로 삼으면 무한 로그아웃 루프가 재발한다 (2026-07-23 실제로 발생했던 버그, 앱 `lib/apiClient.ts` 참조).

**Role permissions:**
| Action | staff | manager | admin |
|--|:--:|:--:|:--:|
| View notices / announcements / schedule / weekly vision | O | O | O |
| Send push notifications | X | X | O (or LMS API Key) |

**This API is read-only for content.** Schedules, announcements, notice posts, and weekly vision are created/edited/deleted **directly in the DB by the LMS** — the Staff API's write routes (`POST/PUT/DELETE` on `/schedule`, `/announcements`, `/bulletin`) were **removed**; only `GET` remains. The one content-mutating endpoint is `POST /notifications/send` (admin JWT or LMS `X-API-Key`). Per-user self-service writes remain: `PATCH /users/me` (profile) and `POST /users/me/password`.

**The `/bulletin` read endpoints were also removed (2026-07, security):** they read the **same `t_noticeboard` table** as `/notices` but applied **no branch (`bid`) filter**, so any staff user could read another branch's notices via `GET /bulletin/{id}` — a cross-branch IDOR that bypassed the exact protection `/notices` adds. `/notices` (branch-scoped, IDOR-safe) fully replaces it and the app only ever used `/notices`. The `BulletinPost` model (`app/models/bulletin.py`) is **kept** — `notice_service` maps it to `t_noticeboard`; only the bulletin controller/service/schema and its router registration were deleted.

Announcement `target_role` visibility: staff sees `all/staff`, manager/admin see `all/staff/manager` (`announcement_service._VISIBLE_ROLES`). This visibility (plus the publish/expire window) is enforced on **both** the list and the single `GET /announcements/{id}` fetch, so a lower role can't read a higher-targeted (or unpublished/expired) announcement by iterating ids.

## Attendance QR Flow (2026-07-22 단순화 — 폴링 제거, 하루 다중 기록)

The employee app generates the QR client-side; an external scanner reads it. The server auto-determines checkin vs checkout based on today's latest record.

1. Frontend: constructs a static token `e{user.id}` (not a JWT) from the authenticated user's ID and renders it as a QR image client-side. **폴링 없음** — 앱은 QR을 표시만 하고(탭 → QR + "Scan at the terminal" + Close) 스캔 결과를 서버에 묻지 않는다. `GET /attendance/qr/status`는 **제거됨** (구 폴링 계약·baseline 로직·2분 만료는 모두 폐기).
2. Scanner: `POST /api/v1/attendance/scan` `{ token, ip, device }` — parses `e{user.id}` format, auto-determines checkin/checkout, records attendance; no auth required. Both `process_scan` and `process_manual` validate that the parsed id is a **real, active** user (`del_yn='N'`) before inserting — a nonexistent/terminated id gets 404, not a junk row.
3. **`t_usertimecheck`는 하루 여러 행 허용** (LMS와 동일, 2026-07-22 변경): 오늘의 최신 행에 checkout이 없으면 그 행에 checkout, 아니면(첫 스캔이거나 모두 완료) 새 행에 checkin. 구 "하루 1행 + 3번째 스캔 409" 로직은 제거됨. 연속 스캔으로 0분짜리 in/out 행이 생길 수 있으나 의도적으로 허용(가드 없음 — LMS에서 수정 가능). 최신 행 판정은 `checkin DESC, id DESC` (DATETIME 초 단위 타이브레이크). **수용된 한계 (owner 확인 2026-07-23): ET 자정을 넘기는 근무는 없다는 전제** — 미완료 행 탐색이 "오늘(ET)" 범위라 자정 넘긴 퇴근 스캔은 새 출근 행이 되지만, 해당 근무 형태가 없으므로 수정하지 않음. 재보고 금지.
4. `GET /attendance/today`와 `GET /attendance/calendar`의 각 날짜는 `records` 배열(checkin 오름차순, `{id, checkin, checkout}`)로 하루 전체 in/out 쌍을 반환한다. 기존 단일 `checkin`(첫 출근)/`checkout`(마지막 행의 퇴근, 미완료면 null) 필드는 구버전 앱 호환용으로 유지. 시간 합산은 하지 않는다.

**Security note (accepted design):** `/scan` and `/manual` are intentionally **unauthenticated** — an external scanner/kiosk calls them and can't carry a staff JWT. This means the `e{user.id}` token is guessable and `ip`/`device` are client-supplied, so buddy-punching is possible by design; this is a **known, accepted trade-off** (mitigated by the per-IP rate limit `SCAN_LIMIT` 120/60s and the active-user check above). Do NOT "fix" it by adding auth — that breaks the scanner. A real fix would require a scanner-side shared secret/HMAC or Apache source-IP restriction, which is a deployment decision, not an app change.

Kiosk alternative: `POST /api/v1/attendance/manual` `{ wid, ip, device }` — bypasses QR, uses `t_user.id` directly. Same checkin/checkout logic applies.

`t_usertimecheck` allows **multiple rows per day** (2026-07-22, LMS와 동일) — each row is one in/out pair. Server logic: latest today row has no checkout → set checkout on it; otherwise → new row with checkin. No 409.

"Today" is determined using Eastern Time (`APP_TZ` in `app/core/constants.py`). 저장값이 ET 벽시계 naive이므로 `today_start_et()`(ET 자정 naive)로 **변환 없이** 비교한다 — UTC 변환 금지 (2026-07-23 정정, Datetime storage contract 참조).

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

## Holidays & Attendance Calendar

Read-only holiday feed over `t_datelist` + holiday/dayoff-aware attendance views. Code: `app/models/datelist.py`, `app/services/holiday_service.py`, `app/controllers/holidays.py`, calendar/day-info logic in `attendance_service`.

- `GET /api/v1/holidays?from_date&to_date` (auth: `get_current_user`) — holidays visible to the caller: `bid IS NULL` (all branches) **or** `bid LIKE '%"<user.bid>"%'`. Defaults to the current month (ET).
- `GET /api/v1/attendance/calendar?year&month` — every day of the month with merged status: `worked` (attendance record exists — holiday name still included alongside, "휴일 근무") → `holiday` → `dayoff` → `none`, plus a `summary` (worked/holiday/dayoff day counts). Defaults to the current month (ET).
- `GET /api/v1/attendance/today` — now also returns `day_info` (`is_holiday`, `holiday_name`, `is_day_off`, all-day vs partial + `stime`/`etime`) — additive, old clients unaffected.
- Dayoffs come from the user's own `t_schedule` (via `t_user.tid`) where `eventtype ∈ DAYOFF_EVENT_TYPES` (`app/core/constants.py`, currently `{"dayoff"}` — extend as the LMS confirms more non-working types). Multi-day spans are expanded per-day; partial dayoffs (`allday='N'` with `stime`/`etime`) are flagged as non-all-day.
- Holidays never block scans (`/scan`, `/manual`) — holiday work is recorded normally and shown as worked + holiday name.
- Weekends are **not** hardcoded as off — branches have different working days; only `t_datelist`/`t_schedule` decide.
- `dev_seed.sql` (repo root) has local-only sample data: 2026 federal holidays, branch-holiday examples, dayoff schedules. Never run it in production.

## Rate Limiting

App-level, in-memory sliding-window limiter (`app/core/rate_limit.py`) applied via `Depends(rate_limit(limit, window, scope))` — login (brute force) and the unauthenticated attendance scan (flooding). Per-process (fine for the single-process deployment; limits become per-worker if scaled).

**Deployment note:** the API runs behind **Apache2** (`mod_proxy_http`) on Ubuntu (managed by systemd). Apache appends the real client IP to the **end** of `X-Forwarded-For`, so `_client_ip()` reads the **rightmost** value. Using the first value would let a client spoof `X-Forwarded-For` to get a fresh bucket per request and bypass every limit.

## DB Notes

Alembic is not used — models are written to match existing DB tables directly.

The app runtime uses `settings.ASYNC_DATABASE_URL` (aiomysql). The `ASYNC_DATABASE_URL` property in `config.py` auto-converts `DATABASE_URL` from pymysql → aiomysql.

`t_user.id` is stored in the JWT `sub` claim. **`t_usertimecheck.wid` stores `t_user.id`** (the PK, not the employee number). `t_user.bid` is the branch/location ID. Note: the notice **read** path (`usp_selnoticeboard`/`usp_selnoticedetail`, `notice_service`) treats `t_noticeboard.wid` as `t_user.id` (author). Since the Staff API no longer writes notices (the LMS writes them directly to the DB), the LMS must set `wid = t_user.id` for "noticed by" to resolve correctly.

**`wid` naming trap:** `wid` means different things per table. `t_usertimecheck.wid` = `t_user.id` (subject). `t_noticeboard.wid` = `t_user.id` (author). `t_schedule.wid` = **writer** `t_user.id` (who entered the row — NOT the schedule's subject; the subject is `tid` for teachers or `uid` for staff). `t_user.wid` is the **registrar's** `t_user.id` (who registered the account — confirmed by the owner 2026-07-22), not an employee number — many accounts share the same value. It plays no role in attendance/QR.

**Schedule (`t_schedule`):** two subject keys (2026-07 schema change: `tid` became nullable, `uid` added). Teacher schedules use `tid` (`t_teacher.tid`, linked from `t_user.tid`); non-teacher staff schedules use `uid` (= `t_user.id`) with `tid=NULL`. `schedule_service` matches `uid = user.id OR tid = user.tid` (tid clause skipped when the user has no tid). LMS write rule: teacher event → set `tid`; staff event → `tid=NULL, uid=t_user.id`; `wid` = writer in both cases. Events can span dates (`sdate`~`edate`, `edate` may be NULL for single-day); range queries must use overlap logic (`sdate <= to AND COALESCE(edate, sdate) >= from`), not `sdate BETWEEN`. `eventtype` values seen: `class`, `tutor`, `dayoff`, `other`. Dayoffs can be partial-day (`stime`/`etime` set, `allday='N'`).

**Holidays (`t_datelist`):** date-dimension table, one row per calendar date (PK `sdate`, range 2014–2030), columns `weekday`, `holidayyn` CHAR(1), `holidaynm`, `bid` (added in `changelog.sql` 2026-07-09). `bid` is a JSON-array **string** in the same format as `t_invoiceitem.bid` (e.g. `'["6","7","4"]'`, values are stringified `t_branch.bid`): `NULL` = holiday for **all** branches (national holidays), array = only those branches (e.g. branch founding day). Branch match uses `bid LIKE '%"<bid>"%'` — the quotes prevent `"2"` from matching `"12"`; don't use `JSON_CONTAINS` (a malformed row would raise). Because PK is `sdate` and every date row already exists, LMS updates must use `INSERT ... ON DUPLICATE KEY UPDATE` — `INSERT IGNORE` silently skips existing dates. One row per date ⇒ a date can carry only **one** holiday name/bid set (a global and a branch holiday can't coexist on the same date). Holiday flags are maintained per-year by the LMS (US federal holidays); verify the current year is populated before relying on it.

**Soft deletes:** legacy tables use a `del_yn` / `delyn` CHAR(1) column (`'N'` = active, `'Y'` = deleted). Services must filter `del_yn = 'N'` on reads. Newer tables (e.g. `t_weekly_vision`) use `is_hidden` instead.

Passwords are stored using MySQL `PASSWORD()` format (`*` + uppercase SHA1(SHA1(plain))). `verify_password` in `security.py` replicates this — passlib/bcrypt is not used.

## Tests

No test suite exists yet. `tests/` contains only `__init__.py`.

## Constants

`app/core/constants.py` holds app-wide constants. Currently:
- `APP_TZ` — `ZoneInfo("America/New_York")` (Eastern Time, covers NY and GA locations)
- `DAYOFF_EVENT_TYPES` — `t_schedule.eventtype` values treated as "not working" for attendance views (currently `{"dayoff"}`)
