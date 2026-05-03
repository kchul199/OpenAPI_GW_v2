# 🛡 운영자 매뉴얼 (Operations Runbook)

## 1. 배포 및 확장 (Kubernetes)
- **Gateway**: 트래픽 증가 시 `gateway-hpa`에 의해 자동으로 파드가 늘어납니다.
- **Redis**: 게이트웨이의 심장부입니다. 반드시 `Persistence`가 활성화된 상태로 운영하십시오.

## 2. 모니터링 포인트
- **Prometheus**: `http://<gateway>:8080/metrics`에서 수집.
- **핵심 지표**:
  - `gateway_requests_total`: 초당 요청 수 (RPS)
  - `gateway_request_duration_seconds`: 응답 지연 시간 (Latency)
  - `gateway_circuit_breaker_open`: 서킷 브레이커 작동 여부

## 3. 긴급 조치 (Troubleshooting)
### 설정 동기화가 안 될 때
1. Admin 서버 로그 확인: Redis 연결 오류 여부.
2. Gateway 로그 확인: Pub/Sub 메시지 수신 여부.
3. 조치: Admin API의 `/api/v1/reload`를 다시 호출하여 강제 동기화.

### 429 Too Many Requests 에러 급증
- 특정 클라이언트의 공격이거나 임계치가 너무 낮게 설정된 경우입니다. `routes.yaml`에서 `limit` 값을 조정하십시오.
