# Staff API 푸시 알림 발송 연동 명세 (v1.1 — 2026-08-12)

LMS → Staff API 푸시 발송 연동 문서. LMS가 이 API를 호출하면 Staff API가 대상자 조회,
FCM/Expo 발송, 알림함 기록, 읽음 추적까지 전부 처리한다.

## 1. 엔드포인트

```
POST https://staff-app.prestigei.com/api/v1/notifications/send
```

## 2. 인증 헤더

```
Content-Type: application/json
X-API-Key: <공유 시크릿>
```

- `X-API-Key` 값 = staff-api 서버 `.env`의 `LMS_API_KEY` 값 (별도 안전한 경로로 전달)
- LMS 설정 파일에 보관할 것 — 코드 하드코딩 금지

## 3. 요청 Body — 전체 필드

```json
{
  "title": "3월 급여명세서 안내",
  "body": "확인해주세요. <b>HTML 사용 가능</b>",
  "user_ids": [12, 45, 2288],
  "data": {
    "route": "/(tabs)/notifications",
    "imageUrl": "https://example.com/poster.jpg",
    "youtubeCode": "dQw4w9WgXcQ"
  }
}
```

| 필드 | 필수 | 타입 | 규칙 |
|---|---|---|---|
| `title` | ✅ | string | 최대 300자. HTML 가능. 배너에는 태그 제거된 평문으로 표시 |
| `body` | ✅ | string | 최대 10,000자. HTML 가능 (이미지 태그, 링크 등) — 배너에는 평문, 앱 알림 상세에서는 HTML 렌더링. `<iframe>`은 앱에서 차단됨 |
| `user_ids` | 권장 | int 배열 \| null | **`t_user.id` 배열** (LMS와 같은 DB — 그대로 사용). 최대 5,000개. 지점/그룹→개인 id 변환은 LMS 책임. 존재하지 않는 id·퇴사자(`del_yn='Y'`)는 서버가 자동 필터. **생략 또는 null = 전 직원 발송**, 빈 배열 `[]` = 아무에게도 발송 안 함 |
| `data` | 선택 | object | 부가 정보. **모든 값은 문자열** (FCM 제약). 하위 필드는 아래 표 |

### `data` 하위 필드 (전부 선택 — 없으면 해당 기능 미표시)

| 키 | 규칙 |
|---|---|
| `route` | 배너 탭 시 이동할 앱 화면. 허용값 4개: `/(tabs)`(홈) · `/(tabs)/notifications`(알림함) · `/(tabs)/attendance`(출퇴근) · `/(tabs)/profile`(프로필). **생략하면 해당 알림의 상세 화면으로 바로 이동** (일반적으로 생략 권장). 허용값 외는 무시됨 |
| `imageUrl` | 이미지 주소, **https 필수**. 앱 알림 상세에 이미지 카드로 표시 + **Android 배너에 큰 이미지**로 표시 (iOS 배너는 텍스트만, 상세에서는 표시됨) |
| `youtubeCode` | 유튜브 영상 코드 (URL 말고 코드만 — `https://youtu.be/dQw4w9WgXcQ`의 `dQw4w9WgXcQ` 부분). 상세에 썸네일+재생버튼으로 표시, 탭하면 유튜브로 이동. 자동재생 없음 |
| `notification_id` | ⚠️ **서버 예약 키 — LMS가 넣지 말 것** (넣어도 서버가 덮어씀) |

### ⚠️ 필드 이름 정확히

위에 명시된 필드 외의 **최상위 키**를 보내면 `422`로 전체 거부된다 (오타로 인한
오발송 방지 장치). 예: `user_ids`를 `userIds`로 보내면 발송되지 않고 에러가 난다 —
의도된 동작. (`user_ids` 오타가 무시되면 "필드 없음 = 전 직원 발송"으로 해석되는
사고가 나기 때문. 2026-08-11 실제 발생 후 도입된 가드.)

## 4. 응답

**성공 — `200`** (즉시 반환, 실제 발송은 백그라운드 처리):

```json
{"message": "Notification sent"}
```

LMS는 응답을 기다리며 대기할 필요 없음. 발송 결과는 DB에서 확인 가능:

- `t_notification_log`: `status`(`pending`→`sent`/`failed`), `push_response`(`success=N failure=M`), `sent_at`
- `t_notification_recipient`: 수신자별 읽음 여부 (`is_read`, `read_at`)

**에러:**

| 코드 | 의미 | 대응 |
|---|---|---|
| `401` | 인증 정보 없음 | `X-API-Key` 헤더 확인 |
| `403` | API 키 값 불일치 | 키 값 확인 |
| `422` | 요청 형식 오류 (필수 필드 누락, 길이 초과, 알 수 없는 필드) | 응답 body의 `detail`에 원인 명시됨 |
| `500` | 서버 오류 | 재시도 또는 staff-api 관리자 문의 |

## 5. 동작 참고사항

- **문자 인코딩**: UTF-8 — 한국어/영어/혼용 모두 지원 (검증 완료)
- **예약 발송**: 이 API는 호출 즉시 발송. 스케줄링은 LMS 쪽 스케줄러 담당
- **앱 버전**: 구버전(Expo 토큰)/신버전(FCM 토큰) 앱 모두 서버가 자동 분기 — LMS는 신경 쓸 필요 없음
- **읽음 동기화**: 한 계정이 여러 기기를 써도 읽음 상태는 계정 단위로 동기화
- **호출 예시 (curl)**:

```bash
curl -X POST https://staff-app.prestigei.com/api/v1/notifications/send \
  -H "X-API-Key: 발급받은키" -H "Content-Type: application/json" \
  -d '{"title":"공지","body":"내용","user_ids":[12,45],"data":{"imageUrl":"https://example.com/a.jpg"}}'
```

---

변경 이력:
- v1.1 (2026-08-12): `data.imageUrl`/`data.youtubeCode` 추가, route 생략 시 상세 직행, 알 수 없는 필드 422 거부
- v1.0 (2026-06): 최초 계약 (title/body/user_ids/data.route)
