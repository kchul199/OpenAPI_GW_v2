# 🛡 운영자 매뉴얼 (Operations Runbook)

이 문서는 프로덕션(운영) 환경에서 OAG를 **배포(Deploy), 모니터링(Monitor), 유지보수(Maintain)**하고 장애 상황에서 조치하는 방법을 설명합니다. 시스템 엔지니어 및 DevOps를 위한 가이드입니다.

---

## 1. 운영 환경 배포 가이드 (Kubernetes)

OAG는 쿠버네티스 환경에 최적화되어 있습니다. `deployments/kubernetes/` 폴더 내의 매니페스트(YAML)를 사용하여 배포합니다.

### 1.1 핵심 컴포넌트 배포
* **Redis**: 게이트웨이의 라우트 설정과 히스토리를 저장하는 **"심장부"**입니다.
  * ⚠️ **경고**: 반드시 `AOF(Append Only File)` 또는 `RDB` 방식으로 **Persistence(영속성)를 활성화**해야 합니다. Redis 파드가 재시작되더라도 라우트 설정이 날아가지 않도록 보장해야 합니다.
  * 클러스터 모드를 사용할 경우 `settings.py` (또는 환경변수 `OAG_REDIS__CLUSTER_MODE=true`) 설정을 켜주세요.
* **Admin API**: `05-admin.yaml`을 사용해 배포합니다. 트래픽을 처리하지 않으므로 레플리카(Replica)는 1~2개로 충분합니다. 보안을 위해 외부망에 직접 노출하지 않고 내부망 또는 VPN을 통해서만 접근하도록 설정하세요.
* **Gateway**: `06-gateway.yaml`을 사용해 배포합니다. 실제 트래픽을 받습니다. `HorizontalPodAutoscaler (HPA)`를 설정하여 CPU/Memory 사용량에 따라 파드가 자동으로 늘어나고 줄어들도록(`Scale In/Out`) 구성하십시오.

### 1.2 중요 환경 변수(Environment Variables) 설정
배포 시 다음 환경변수를 `.env`나 K8s ConfigMap/Secret으로 주입해야 합니다.
* `OAG_ENVIRONMENT`: `production`으로 설정.
* `OAG_REDIS__URL`: `redis://redis-svc:6379/0` (Redis 주소)
* `OAG_ADMIN__API_KEY`: Admin API를 조작할 수 있는 **마스터 키**입니다. 매우 길고 복잡한 무작위 문자열로 변경하세요!

---

## 2. 관측성 및 모니터링 (Observability)

OAG는 내부 상태를 투명하게 공개하여 운영자가 즉각적으로 문제를 파악할 수 있도록 돕습니다.

### 2.1 메트릭 모니터링 (Prometheus & Grafana)
* **엔드포인트**: `http://<gateway-pod-ip>:8080/metrics`
* **반드시 모니터링하고 알람(Alert)을 걸어야 할 핵심 지표**:
  * `gateway_requests_total`: 초당 들어오는 요청 수 (RPS). 갑작스러운 트래픽 폭증(DDoS 등) 파악.
  * `gateway_request_duration_seconds`: API 응답 지연 시간 (Latency). 이 값이 높아지면 백엔드 서버나 네트워크에 문제가 있는 것입니다.
  * `gateway_circuit_breaker_open`: 서킷 브레이커가 작동(차단)된 횟수. 백엔드 서비스의 장애를 즉각적으로 알 수 있습니다.
  * `admin_auth_failures_total`: Admin API 인증 실패 횟수. 비정상적으로 높으면 누군가 해킹을 시도 중인 것입니다.

### 2.2 로그 (Structured JSON Logging)
* `settings.py`에서 `log_format=json`으로 설정하면, 로그 수집기(Fluentbit, ELK 스택, Datadog 등)가 파싱하기 쉬운 JSON 형태로 로그가 남습니다.
* 에러 로그 추적 시 `request_id` 필드를 사용해 게이트웨이부터 백엔드까지의 요청 흐름을 추적하세요.

---

## 3. 관리자 권한 및 키 로테이션 (Admin RBAC)

Admin API 키가 유출되었거나, 정기적인 보안 업데이트가 필요할 때의 조치 방법입니다.

* **키 로테이션 (Key Rotation)**
  1. `POST /api/v1/admin/keys/rotate` API를 호출합니다. (새로운 키 생성 및 유효기간 설정 가능)
  2. 응답으로 받은 새로운 키를 CI/CD 파이프라인이나 스크립트에 업데이트합니다.
  3. 기존 키를 무효화하려면 `POST /api/v1/admin/keys/{old_key_id}/deactivate`를 호출합니다.
* **IP 화이트리스트 적용**: `OAG_ADMIN__ALLOWED_IPS` 환경변수에 회사 내부망 IP(`10.0.0.0/8`, `192.168.1.0/24` 등)를 쉼표로 구분해 넣으면, 외부에서 Admin API로 접근하는 것을 원천 차단할 수 있습니다.

---

## 4. 긴급 조치 및 트러블슈팅 (Troubleshooting)

### 상황 A. "설정을 바꿨는데 게이트웨이에 반영이 안 돼요!"
* **원인**: Admin API가 Redis로 Pub/Sub 이벤트를 보냈으나, Gateway 파드들이 이를 받지 못했을 가능성이 큽니다. (주로 일시적인 네트워크 단절)
* **조치 방법**:
  1. Admin API를 통해 강제 동기화 API를 호출합니다: `curl -X POST http://admin:9000/api/v1/reload -H "X-Admin-Key: <your_key>"`
  2. 그래도 안 된다면, Gateway 파드의 로그를 확인하여 Redis 접속 에러(Timeout 등)가 있는지 확인하세요.

### 상황 B. "클라이언트들이 자꾸 429 (Too Many Requests) 에러를 받아요!"
* **원인**: `RateLimitPlugin`의 제한치(`limit`)를 초과했습니다. 실제 악의적인 트래픽 폭증이거나, 설정된 임계치가 너무 낮은 경우입니다.
* **조치 방법**:
  1. Admin API에서 해당 라우트의 설정을 조회합니다: `GET /api/v1/routes/{route_id}`
  2. 트래픽이 정당한 것이라면, `limit` 값을 상향 조정한 뒤 `PUT /api/v1/routes/{route_id}`로 업데이트합니다. 즉시 반영되어 에러가 해소됩니다.

### 상황 C. "잘못된 라우팅 설정으로 서비스 전체가 멈췄어요!"
* **원인**: 휴먼 에러로 인해 정상적인 라우트를 삭제했거나 타겟 URL을 잘못 적은 경우.
* **조치 방법**: **롤백 기능**을 사용합니다.
  1. `GET /api/v1/routes/history`를 호출해 방금 전의 엉망이 된 작업(`entry_id`)을 찾습니다.
  2. `POST /api/v1/routes/history/{entry_id}/rollback`을 호출하여 시스템을 그 이전의 안전한 상태로 즉시 되돌립니다.
