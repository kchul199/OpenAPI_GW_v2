# 🔌 연동 규격서 (Interface Specification)

## 1. Gateway 트래픽 API (Port 8080 / 9090)
클라이언트가 백엔드 서비스에 접근하기 위해 사용하는 경로입니다.

### 공통 헤더
- `X-Request-ID`: 요청의 고유 식별자 (응답 시에도 반환됨).

## 2. Admin 관리 API (Port 9000)
게이트웨이 설정을 제어하기 위한 API입니다. 모든 요청에는 `X-Admin-Key` 헤더가 필요합니다.

### 2.1 헬스체크 및 상태
- **URL**: `GET /api/v1/health`
- **응답**:
```json
{
  "status": "ok",
  "routes_loaded": 12
}
```

### 2.2 라우트 관리
- `GET /api/v1/routes`: 전체 라우트 목록 조회
- `POST /api/v1/routes`: 신규 라우트 생성
- `PUT /api/v1/routes/{id}`: 기존 라우트 수정
- `DELETE /api/v1/routes/{id}`: 라우트 삭제

## 3. 플러그인 상세 설정
- **rate-limiter**: `limit`(횟수), `window`(초), `key_func`(`ip`|`user`|`api_key`)
- **jwt-validator**: `secret_key`(시크릿), `algorithm`(`HS256`|`RS256`)
- **circuit-breaker**: `failure_threshold`(실패 횟수), `recovery_timeout`(복구 시간)
