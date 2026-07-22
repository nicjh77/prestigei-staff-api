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
-- ⚠️ 신규 서버 코드 배포 후 안정 확인이 끝나면 수동 실행 (코드가 참조하지 않으므로 즉시 실행 필수 아님):

-- DROP TABLE `t_refresh_tokens`;

-- 함께 변경된 env 설정 (.env.production에 직접 반영 필요):
--   ACCESS_TOKEN_EXPIRE_MINUTES=4320   (3일)
--   REFRESH_TOKEN_EXPIRE_DAYS 삭제
--   QR_CODE_VALIDITY_MINUTES 삭제 (미사용이었음 — QR 폴링/만료 개념 제거)

-- 참고 (스키마 변경 아님): 같은 배포에서 t_usertimecheck는 "하루 여러 in/out 행" 방식으로
-- 전환됨 (LMS와 동일). 컬럼 변경 없음 — 서버 로직만 변경 (3번째 스캔 409 → 새 행 체크인).
