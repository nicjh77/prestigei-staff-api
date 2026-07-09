-- =====================================================================
-- dev_seed.sql — 로컬 개발용 샘플 데이터 (프로덕션 실행 금지)
-- attendance 캘린더 / 휴일 / 휴가 기능 테스트용.
-- 실행: mysql -u root -p prestigei < dev_seed.sql  (또는 워크벤치에서 실행)
-- =====================================================================

-- ---------------------------------------------------------------
-- 1) t_datelist — 2026년 연방 공휴일 (전 지점 공통, bid = NULL)
--    PK(sdate) 행이 이미 존재하므로 INSERT IGNORE 불가 → ON DUPLICATE KEY UPDATE
-- ---------------------------------------------------------------
INSERT INTO `t_datelist` (`sdate`, `weekday`, `holidayyn`, `holidaynm`, `bid`) VALUES
    ('2026-01-01', 'THURSDAY',  'Y', 'New Year''s Day',              NULL),
    ('2026-01-19', 'MONDAY',    'Y', 'Martin Luther King Jr. Day',   NULL),
    ('2026-02-16', 'MONDAY',    'Y', 'Presidents'' Day',             NULL),
    ('2026-05-25', 'MONDAY',    'Y', 'Memorial Day',                 NULL),
    ('2026-06-19', 'FRIDAY',    'Y', 'Juneteenth',                   NULL),
    ('2026-07-03', 'FRIDAY',    'Y', 'Independence Day (observed)',  NULL),
    ('2026-07-04', 'SATURDAY',  'Y', 'Independence Day',             NULL),
    ('2026-09-07', 'MONDAY',    'Y', 'Labor Day',                    NULL),
    ('2026-10-12', 'MONDAY',    'Y', 'Columbus Day',                 NULL),
    ('2026-11-11', 'WEDNESDAY', 'Y', 'Veterans Day',                 NULL),
    ('2026-11-26', 'THURSDAY',  'Y', 'Thanksgiving Day',             NULL),
    ('2026-12-25', 'FRIDAY',    'Y', 'Christmas Day',                NULL)
ON DUPLICATE KEY UPDATE
    `weekday` = VALUES(`weekday`),
    `holidayyn` = VALUES(`holidayyn`),
    `holidaynm` = VALUES(`holidaynm`),
    `bid` = VALUES(`bid`);

-- ---------------------------------------------------------------
-- 2) t_datelist — 지점별 휴일 예시 (bid = JSON 배열 문자열)
--    지점: 1=BS 2=WC 3=CL 4=PP 6=HQ 7=ON 8=SW 9=HA 11=WE 12=CU 13=CK 14=AP 15=OT
-- ---------------------------------------------------------------
INSERT INTO `t_datelist` (`sdate`, `weekday`, `holidayyn`, `holidaynm`, `bid`) VALUES
    ('2026-07-15', 'WEDNESDAY', 'Y', 'WC Founding Day',        '["2"]'),
    ('2026-07-20', 'MONDAY',    'Y', 'PP/SW Branch Holiday',   '["4","8"]')
ON DUPLICATE KEY UPDATE
    `weekday` = VALUES(`weekday`),
    `holidayyn` = VALUES(`holidayyn`),
    `holidaynm` = VALUES(`holidaynm`),
    `bid` = VALUES(`bid`);

-- ---------------------------------------------------------------
-- 3) t_schedule — 휴가(dayoff) 샘플
--    tid는 본인 테스트 계정 것으로 변경:
--      SELECT id, loginid, tid, bid FROM t_user WHERE loginid = '<내 로그인 ID>';
--    (로컬 참고: tid=14 → user 2097 David WJ Lee / tid=78 → user 2202 Jangho Lee)
-- ---------------------------------------------------------------
SET @tid := 14;   -- ← 본인 계정의 t_user.tid 로 변경
SET @wid := 1;    -- 작성자 t_user.id (아무 관리자 id)

-- 종일 스팬 휴가: 7/27(월) ~ 7/29(수)
INSERT INTO `t_schedule` (`tid`, `wid`, `sdate`, `edate`, `stime`, `etime`, `allday`, `eventname`, `eventtype`, `ins_date`)
VALUES (@tid, @wid, '2026-07-27', '2026-07-29', NULL, NULL, 'Y', 'Summer Vacation', 'dayoff', NOW());

-- 부분 휴가: 7/31(금) 14:00~17:00
INSERT INTO `t_schedule` (`tid`, `wid`, `sdate`, `edate`, `stime`, `etime`, `allday`, `eventname`, `eventtype`, `ins_date`)
VALUES (@tid, @wid, '2026-07-31', '2026-07-31', '14:00', '17:00', 'N', 'Doctor Appointment', 'dayoff', NOW());

-- ---------------------------------------------------------------
-- 3-1) 일반 직원(티처 아님) 휴가 — tid=NULL, uid=t_user.id
--      SELECT id, loginid FROM t_user WHERE tid IS NULL AND del_yn='N';
-- ---------------------------------------------------------------
SET @staff_uid := 2077;  -- ← 테스트할 일반 직원의 t_user.id 로 변경

INSERT INTO `t_schedule` (`tid`, `uid`, `wid`, `sdate`, `edate`, `stime`, `etime`, `allday`, `eventname`, `eventtype`, `ins_date`)
VALUES (NULL, @staff_uid, @wid, '2026-07-23', '2026-07-24', NULL, NULL, 'Y', 'Personal Leave', 'dayoff', NOW());

-- ---------------------------------------------------------------
-- 4) t_usertimecheck — 출근 기록 샘플 (선택)
--    wid 는 t_user.id (tid 아님!). 필요 시 주석 해제 후 id 변경.
--    시간은 UTC 저장 — 아래는 ET 09:00/18:00 (EDT = UTC-4)
-- ---------------------------------------------------------------
-- SET @uid := 2097;  -- ← 본인 t_user.id 로 변경
-- INSERT INTO `t_usertimecheck` (`wid`, `checkin`, `checkout`) VALUES
--     (@uid, '2026-07-06 13:00:00', '2026-07-06 22:00:00'),
--     (@uid, '2026-07-07 13:05:00', '2026-07-07 22:10:00'),
--     (@uid, '2026-07-08 12:55:00', NULL);
