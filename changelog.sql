-- =============================================
-- 2026-04-06
-- =============================================

CREATE TABLE `t_refresh_tokens` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `token_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `device_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `t_weekly_vision` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content` longtext COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `created_by` int DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` int DEFAULT NULL,
  `is_hidden` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_created_by` (`created_by`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- 2026-06-18  Push Notifications
-- =============================================

CREATE TABLE `t_push_token` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `fcm_token` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `device_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `platform` enum('ios','android') COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_device` (`user_id`, `device_id`),
  KEY `idx_fcm_token` (`fcm_token`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- 2026-06-19  Notification Recipients (읽음/안읽음)
-- =============================================

CREATE TABLE `t_notification_recipient` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `notification_id` bigint NOT NULL,
  `user_id` int NOT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `read_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_notif_user` (`notification_id`, `user_id`),
  KEY `idx_user_read` (`user_id`, `is_read`),
  CONSTRAINT `fk_recipient_notification` FOREIGN KEY (`notification_id`) REFERENCES `t_notification_log` (`id`),
  CONSTRAINT `fk_recipient_user` FOREIGN KEY (`user_id`) REFERENCES `t_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2026-06-18  FCM → Expo Push Token 변경
ALTER TABLE `t_push_token` CHANGE `fcm_token` `push_token` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL;
ALTER TABLE `t_push_token` DROP INDEX `idx_fcm_token`, ADD KEY `idx_push_token` (`push_token`(191));
ALTER TABLE `t_notification_log` CHANGE `fcm_response` `push_response` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL;

CREATE TABLE `t_notification_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `title` varchar(300) COLLATE utf8mb4_unicode_ci NOT NULL,
  `body` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `data` json DEFAULT NULL,
  `status` enum('pending','sent','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `push_response` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sent_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- 2026-07-09  t_datelist 지점별 휴일 지원 (bid 컬럼 추가)
-- =============================================
-- bid: JSON 배열 문자열 — t_invoiceitem.bid 와 동일 형식 (예: '["6","7","4","8","2"]', 값은 t_branch.bid 문자열)
--   NULL       = 전 지점 공통 (국가 공휴일 등)
--   '["4"]' 등 = 해당 지점들만의 휴일 (지점 창립일 등)
-- 컬럼 charset 은 t_datelist 기존 컬럼과 동일하게 utf8mb3 유지

ALTER TABLE `t_datelist`
  ADD COLUMN `bid` varchar(255) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL AFTER `holidaynm`;

-- ⚠️ LMS 주입 시 주의: 2014-01-01 ~ 2030-12-31 전 날짜 행이 이미 존재하므로 (PK = sdate)
-- INSERT IGNORE 는 기존 날짜에 대해 아무것도 갱신하지 않음 (조용히 skip).
-- 기존 날짜의 휴일 지정/변경은 ON DUPLICATE KEY UPDATE 사용:
--
-- INSERT INTO `t_datelist` (`sdate`, `weekday`, `holidayyn`, `holidaynm`, `bid`) VALUES
--     ('2026-07-04', 'SATURDAY', 'Y', 'Independence Day', NULL),
--     ('2026-09-15', 'TUESDAY',  'Y', 'WC Founding Day', '["2"]')
-- ON DUPLICATE KEY UPDATE
--     `weekday` = VALUES(`weekday`),
--     `holidayyn` = VALUES(`holidayyn`),
--     `holidaynm` = VALUES(`holidaynm`),
--     `bid` = VALUES(`bid`);


-- =============================================
-- 2026-07-09  t_schedule 일반 직원 일정 지원 (tid nullable + uid)
-- =============================================
-- 아래 두 건은 이미 프로덕션/로컬에 적용되어 있음 (기록용):
--   ALTER TABLE `t_schedule` MODIFY `tid` int NULL;                 -- 티처 일정만 tid 사용
--   ALTER TABLE `t_schedule` ADD COLUMN `uid` int NULL AFTER `tid`; -- 일반 직원 일정 대상 = t_user.id
-- 입력 규칙 (LMS): 티처 일정 → tid 세팅 / 일반 직원 일정 → tid=NULL, uid=t_user.id / wid = 작성자 t_user.id

-- uid 조회 인덱스 (Staff API가 WHERE uid = ... 로 조회) — 프로덕션에 이미 존재 확인됨 (2026-07-09, 기록용)
--   ALTER TABLE `t_schedule` ADD KEY `idx_uid` (`uid`);


-- =============================================
-- 2026-07-22  리프레시 토큰 제거 (LMS 정합 업데이트)
-- =============================================
-- 앱/서버가 리프레시 토큰을 더 이상 사용하지 않음 (액세스 JWT 3일 만료로 대체).
-- ✅ 신규 서버 코드 프로덕션 배포 완료: 2026-07-24 (검증 통과 — MIN_VERSION 1.2.0, /daily-log/tasks 라이브)
-- ⚠️ 안정 확인(다음 주) 후 수동 실행 (코드가 참조하지 않으므로 즉시 실행 필수 아님):

-- DROP TABLE `t_refresh_tokens`;

-- 함께 변경된 env 설정 (.env.production에 직접 반영 필요):
--   ACCESS_TOKEN_EXPIRE_MINUTES=4320   (3일)
--   REFRESH_TOKEN_EXPIRE_DAYS 삭제
--   QR_CODE_VALIDITY_MINUTES 삭제 (미사용이었음 — QR 폴링/만료 개념 제거)

-- 참고 (스키마 변경 아님): 같은 배포에서 t_usertimecheck는 "하루 여러 in/out 행" 방식으로
-- 전환됨 (LMS와 동일). 컬럼 변경 없음 — 서버 로직만 변경 (3번째 스캔 409 → 새 행 체크인).


-- =============================================
-- 2026-09-05  PTO 기능 — LMS 소유 테이블 기록 (프로덕션에 이미 존재, Staff API는 참조만)
-- =============================================
-- 프로덕션에서 export 받아 로컬에 적용 완료 (2026-09-05). 아래는 기록용 DDL.
-- ⚠️ 이 배포는 DB 변경 없음 (코드만). 프로덕션 t_schedule.halfday·t_holiday·t_vacation 이미 존재 확인 (2026-09-05).
-- 서버 코드 커밋 f627e81 — 프로덕션 업로드/재시작은 수동 (CLAUDE.md Deployment 참조).
-- t_schedule.halfday: 프로덕션에 존재하던 컬럼 — 로컬은 2026-09-05 수동 추가:
--   ALTER TABLE `t_schedule` ADD COLUMN `halfday` char(1) DEFAULT 'N' AFTER `allday`;
--
-- t_holiday — 지점별 휴일 (LMS "Manage Holidays"). bid는 int (t_branch.bid). t_datelist.bid(JSON 문자열)와는 별개.
-- CREATE TABLE IF NOT EXISTS `t_holiday` (
--   `id` int NOT NULL AUTO_INCREMENT,
--   `sdate` date NOT NULL,
--   `bid` int NOT NULL,
--   `holidayyn` char(1) DEFAULT 'N',
--   `holidaynm` varchar(255) DEFAULT NULL,
--   PRIMARY KEY (`id`), KEY `id_sdate` (`sdate`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;
--
-- t_vacation — 개인별 연도별 배정 휴가 일수 (HR이 LMS Staff Vacation에서 입력). ayear는 char(4).
-- CREATE TABLE IF NOT EXISTS `t_vacation` (
--   `id` int NOT NULL AUTO_INCREMENT,
--   `userid` int DEFAULT NULL,            -- t_user.id
--   `ayear` char(4) DEFAULT NULL,
--   `fromdate` date DEFAULT NULL,
--   `todate` date DEFAULT NULL,
--   `vacationday` float DEFAULT NULL,
--   `added` datetime DEFAULT NULL, `addedby` int DEFAULT NULL,
--   `updated` datetime DEFAULT NULL, `updatedby` int DEFAULT NULL,
--   `comment` text,
--   PRIMARY KEY (`id`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- 2026-09-08  t_push_token 앱/기기 상태 컬럼 (Profile > About / 사용자 앱 버전 파악) — 학생 앱과 같은 구성
-- =============================================
-- 앱이 토큰 등록(POST /notifications/token) 때 버전·빌드·OTA·기기 정보를 함께 보낸다. 구버전 앱은 안 보내므로 NULL 허용.
-- 서버는 이 값들을 컬럼 폭에 맞춰 잘라 저장한다(거부 안 함 — 긴 os_name이 토큰 등록을 막았던 학생 앱 사례).
-- ✅ 프로덕션 적용 완료 2026-09-08 (서버 재시작과 함께). 아래는 기록용.
ALTER TABLE `t_push_token`
  ADD COLUMN `app_version`  varchar(20) NULL AFTER `is_active`,     -- "1.3.0"
  ADD COLUMN `build_number` varchar(20) NULL AFTER `app_version`,   -- Android versionCode / iOS buildNumber
  ADD COLUMN `ota`          varchar(32) NULL AFTER `build_number`,  -- 'embedded' | 'YYYYMMDD-HHMM' (실행 중 OTA의 ET 발행시각)
  ADD COLUMN `update_id`    varchar(40) NULL AFTER `ota`,           -- expo-updates updateId (OTA일 때만)
  ADD COLUMN `device_model` varchar(80) NULL AFTER `update_id`,
  ADD COLUMN `os_name`      varchar(20) NULL AFTER `device_model`,
  ADD COLUMN `os_version`   varchar(30) NULL AFTER `os_name`,
  ADD COLUMN `last_seen_at` datetime    NULL AFTER `os_version`;    -- 마지막 토큰 등록(앱 실행) 시각, ET 벽시계

-- 확인용: 사용자별 앱 상태
-- SELECT u.loginid, t.platform, t.app_version, t.build_number, t.ota, t.device_model, t.os_version, t.last_seen_at, t.is_active,
--        CASE WHEN t.push_token LIKE 'Expo%' THEN 'expo' ELSE 'fcm' END AS token_kind
-- FROM t_push_token t JOIN t_user u ON u.id = t.user_id ORDER BY t.last_seen_at DESC;


-- =============================================
-- 2026-09-08  t_push_token 같은 폰 잔여 행 정리 (일회성) — 이후는 서버가 토큰 등록 때 자동 비활성화
-- =============================================
-- device_id에 OS 버전이 들어가 OS 업데이트마다 새 행이 생겼고, 옛 Expo 행/같은 FCM 토큰 행이 활성으로 남아
-- 같은 폰에 알림이 두 번 갔다. 아래는 기존 데이터 정리 (신규 등록부터는 notification_service.register_token이 처리).
UPDATE t_push_token e
JOIN t_push_token f
  ON f.user_id = e.user_id AND f.platform = e.platform AND f.id <> e.id AND f.is_active = 1
 AND f.last_seen_at IS NOT NULL                                  -- 새 코드로 등록된(최근 실행) 행을 기준으로
 AND (e.push_token LIKE 'Expo%'                                  -- ① 구버전 Expo 토큰
      OR e.push_token = f.push_token                             -- ② 같은 토큰 중복
      OR SUBSTRING_INDEX(e.device_id, '_', 2) = SUBSTRING_INDEX(f.device_id, '_', 2))  -- ③ 같은 기종·OS, 다른 OS 버전
SET e.is_active = 0
WHERE e.is_active = 1 AND e.last_seen_at IS NULL;
-- 확인: SELECT user_id, device_id, LEFT(push_token,18), is_active, last_seen_at FROM t_push_token ORDER BY user_id, is_active DESC;
