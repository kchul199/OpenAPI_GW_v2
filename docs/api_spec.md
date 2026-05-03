# 🔌 연동 규격서 (Interface Specification)

이 문서는 게이트웨이를 제어하기 위한 **Admin API 명세**와 라우트를 구성할 때 사용하는 **JSON/YAML 스펙 및 플러그인 설정 방법**을 정의합니다. 백엔드 개발자나 자동화 툴(CI/CD)을 구축하는 분들이 참고해야 할 핵심 규격서입니다.

---

## 1. Admin 관리 API (Control Plane)
게이트웨이의 라우팅 정책을 조회하거나 동적으로 변경할 때 사용하는 REST API입니다.
* **기본 포트**: `9000` (예: `http://localhost:9000/api/v1/...`)
* **공통 보안 요구사항**: 모든 API 호출에는 `X-Admin-Key` HTTP 헤더가 반드시 포함되어야 합니다. 읽기(Read) 전용 API는 `read` 권한의 키로, 생성/수정/삭제(Write) API는 `write` 권한 이상의 키로만 접근 가능합니다.

### 1.1 대시보드 및 상태 조회
* **`GET /api/v1/health`**: Admin 서버와 연결된 Redis 중앙 저장소의 상태, 로드된 라우트 개수를 확인합니다.
* **`GET /api/v1/dashboard`**: 현재 게이트웨이의 요약 정보(활성화된 플러그인 수, 라우트 목록 요약, 사용 중인 프로토콜 통계 등)를 반환합니다. (Admin UI에서 주로 사용됨)

### 1.2 라우트(Route) CRUD 관리
라우트(경로 규칙)를 관리하는 핵심 API입니다. 생성/수정/삭제 작업 성공 시 자동으로 모든 게이트웨이에 핫 리로드(Hot-reload) 이벤트가 전송됩니다.

* **전체 조회** (`GET /api/v1/routes`): 현재 등록된 전체 라우트 목록(JSON)을 가져옵니다.
* **단건 조회** (`GET /api/v1/routes/{id}`): 특정 ID의 라우트 상세 설정을 가져옵니다.
* **라우트 검증** (`POST /api/v1/routes/validate`): 작성한 라우트 JSON 스펙이 문법적으로 올바른지 미리 검사합니다(실제 적용 안됨).
* **라우트 생성** (`POST /api/v1/routes`): 새로운 라우트를 생성합니다. (Body에 라우트 JSON 스펙 포함)
* **라우트 수정** (`PUT /api/v1/routes/{id}`): 기존 라우트를 수정합니다. 전체 스펙을 덮어씁니다(Replace).
* **라우트 삭제** (`DELETE /api/v1/routes/{id}`): 특정 라우트를 삭제합니다.

### 1.3 히스토리 및 롤백 (History & Rollback)
관리자가 실수로 라우트를 삭제하거나 잘못 수정한 경우를 대비한 기능입니다.

* **히스토리 조회** (`GET /api/v1/routes/history`): 라우트 변경 이력(누가, 언제, 어떻게 바꿨는지) 목록을 조회합니다. 반환된 항목에는 `entry_id`가 포함되어 있습니다.
* **롤백 실행** (`POST /api/v1/routes/history/{entry_id}/rollback`): 특정 히스토리 지점 이전의 상태로 되돌립니다. 예를 들어, 삭제된 라우트를 복원하거나 잘못 덮어쓴 라우트를 원복할 수 있습니다.

### 1.4 수동 동기화
* **`POST /api/v1/reload`**: 중앙 Redis 저장소의 최신 설정으로 현재 연결된 모든 게이트웨이를 강제로 재동기화 시킵니다.

---

## 2. 라우트 스펙 (Route JSON / YAML)
`/api/v1/routes` API의 Body로 전송하거나 `routes.yaml` 파일에 작성하는 규칙의 기본 구조입니다.

```json
{
  "id": "user-service-route",
  "description": "사용자 관리 API 라우트",
  "match": {
    "protocol": "http",          // http, websocket, grpc 중 택 1
    "path": "/api/v1/users/**",  // ** 는 하위 모든 경로를 포함하는 와일드카드
    "methods": ["GET", "POST"]   // 허용할 HTTP 메서드 목록
  },
  "upstream": {
    "type": "http",
    "targets": [
      {"url": "http://user-service-1:8080", "weight": 1},
      {"url": "http://user-service-2:8080", "weight": 1}
    ],
    "load_balance": "round_robin" // 라운드로빈 방식으로 타겟 분산
  },
  "strip_prefix": true,           // true면 /api/v1/users/profile -> /profile 로 백엔드 전달
  "plugins": [                    // 이 라우트에만 적용할 미들웨어 플러그인 목록
    // 아래 3번 항목의 플러그인 설정 참고
  ]
}
```

---

## 3. 주요 플러그인(Plugins) 설정 스펙
라우트의 `plugins` 배열에 추가하여 사용하는 기능들의 세부 파라미터입니다. (동일한 구조로 `gateway.yaml`의 `global_plugins`에 적용하면 모든 라우트에 일괄 적용됩니다.)

### 3.1 Rate Limiter (트래픽 제한)
IP 주소 등을 기준으로 초당/분당 요청 횟수를 제한하여 서버 과부하를 막습니다.
```json
{
  "name": "rate-limiter",
  "enabled": true,
  "config": {
    "limit": 100,           // 허용할 최대 요청 수
    "window": 60,           // 기준 시간 (초 단위, 예: 60초당 100회)
    "key_func": "ip"        // 제한 기준 (ip, user_id, api_key 등)
  }
}
```

### 3.2 JWT Validator (사용자 인증)
Authorization 헤더에 담긴 JWT 토큰의 유효성(서명 검증, 만료 시간 확인)을 검사합니다.
```json
{
  "name": "jwt-validator",
  "enabled": true,
  "config": {
    "secret_key": "YOUR_SECRET", // 토큰을 검증할 비밀키 (K8s Secret 연동 권장)
    "algorithm": "HS256"         // 암호화 알고리즘 (HS256, RS256 등)
  }
}
```

### 3.3 Circuit Breaker (장애 확산 방지)
백엔드 서버가 지속적으로 오류를 낼 때, 연쇄적인 장애(Time-out 등)를 막기 위해 일시적으로 트래픽을 차단합니다.
```json
{
  "name": "circuit-breaker",
  "enabled": true,
  "config": {
    "failure_threshold": 5,      // 이 횟수만큼 연속 실패(5xx 응답 등)하면 서킷을 엽니다(차단).
    "recovery_timeout": 30       // 서킷이 열린 후 몇 초 뒤에 백엔드가 회복되었는지 다시 확인(반열림)할지 설정
  }
}
```

### 3.4 API Key (서버 대 서버 인증)
클라이언트가 전달하는 API Key를 검사합니다. B2B 연동이나 내부 서비스 간 호출 시 사용합니다.
```json
{
  "name": "api-key",
  "enabled": true,
  "config": {
    "header_name": "X-API-Key",  // 검사할 HTTP 헤더 이름
    "valid_keys": ["key123", "key456"] // 허용된 키 목록 (보안 주의)
  }
}
```
