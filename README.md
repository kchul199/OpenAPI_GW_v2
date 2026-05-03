# 🌌 Open API Gateway (OAG)

Open API Gateway는 고성능 REST, gRPC, WebSocket 트래픽을 처리하고 관리하는 **클라우드 네이티브 API 게이트웨이**입니다. 

## 🌟 핵심 기능
- **멀티 프로토콜 지원**: HTTP/REST, gRPC(Unary/Stream), WebSocket 프록싱.
- **중앙 집중형 설정**: Redis Hash를 통한 전역 설정 관리 및 실시간 동기화.
- **강력한 보안**: K8s Secret 연동, JWT 검증, API Key 관리(RBAC), mTLS.
- **트래픽 제어**: 분산 레이트 리밋(Rate Limit), 서킷 브레이커(Circuit Breaker).
- **관측성**: Prometheus 메트릭, OpenTelemetry 트레이싱, 구조화된 JSON 로깅.

## 🛠 시작하기 (Quick Start)

### 1. 환경 준비
```bash
# 가상환경 생성 및 의존성 설치
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 로컬 실행 (Docker Compose)
모든 인프라(Redis, Mock 서비스 등)를 한 번에 실행합니다.
```bash
./scripts/local-up.sh
```

### 3. 접속 정보
- **Gateway (Traffic)**: `http://localhost:8080`
- **Admin API (Control)**: `http://localhost:9000`
- **Admin UI**: `http://localhost:9000/ui`

## 📚 상세 문서 바로가기
- [🏗 아키텍처 설계서](docs/architecture.md): 시스템 구조 및 기술 스택
- [🔌 연동 규격서](docs/api_spec.md): API 엔드포인트 및 플러그인 설정
- [🛡 운영자 매뉴얼](docs/operations_runbook.md): 배포, 모니터링 및 트러블슈팅
- [📝 사용자 가이드](docs/user_guide.md): 라우트 등록 및 활용 방법
