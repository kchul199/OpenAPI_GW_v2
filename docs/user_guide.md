# 📝 사용자 가이드 (User Guide)

## 1. 신규 라우트 등록하기 (Step-by-Step)
새로운 마이크로서비스를 게이트웨이에 연결하려면 다음 과정을 따르세요.

### 단계 1: 라우트 정의 작성
`routes.yaml` 형식의 JSON/YAML을 준비합니다.
```yaml
id: "my-service"
match:
  path: "/my-api/**"
upstream:
  targets:
    - url: "http://my-service-internal:8000"
```

### 단계 2: Admin API를 통한 등록
```bash
curl -X POST http://localhost:9000/api/v1/routes \
     -H "X-Admin-Key: your-admin-key" \
     -H "Content-Type: application/json" \
     -d @route.json
```

### 단계 3: 적용 확인
이제 `http://gateway:8080/my-api/hello` 호출 시 백엔드로 트래픽이 전달됩니다.

## 2. 보안 적용하기
- **API Key 필요 시**: `plugins` 섹션에 `api-key`를 추가하세요.
- **사용자 인증 필요 시**: `jwt-validator`를 추가하고 토큰 검증 키를 설정하세요.
