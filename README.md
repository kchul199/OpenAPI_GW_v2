# 🌌 Open API Gateway (OAG) v2

**Open API Gateway(OAG)**는 고성능 REST, gRPC, WebSocket 트래픽을 처리하고 관리하기 위해 설계된 **클라우드 네이티브 API 게이트웨이**입니다. Python의 `FastAPI` 기반 비동기(Asynchronous) 아키텍처와 `Redis`를 활용한 분산 상태 관리를 통해 빠르고 안정적인 트래픽 제어 기능을 제공합니다.

---

## 📖 게이트웨이(API Gateway)란 무엇인가요?
API 게이트웨이는 클라이언트(웹 브라우저, 모바일 앱 등)와 백엔드 마이크로서비스들 사이에 위치하는 **"단일 진입점(Single Point of Entry)"**입니다. 
클라이언트가 각각의 백엔드 서버 주소를 알 필요 없이, 모든 요청을 게이트웨이로 보내면 게이트웨이가 알맞은 서버로 요청을 전달(라우팅)해 줍니다. 
그 과정에서 인증, 권한 인가, 요청량 제한(Rate Limit), 로깅 등 공통적인 기능들을 처리합니다.

---

## 🌟 OAG 핵심 기능 (Key Features)

### 1. 다양한 프로토콜 완벽 지원 (Multi-Protocol Proxy)
* **HTTP/REST**: `httpx` 비동기 클라이언트를 활용한 빠르고 안정적인 역방향 프록시(Reverse Proxy).
* **WebSocket**: 양방향 실시간 통신을 위한 웹소켓 프록싱 지원.
* **gRPC**: `grpc.aio`를 활용한 Unary 및 Streaming RPC 호출 지원.

### 2. 동적 무중단 설정 (Hot-Reloading)
* **Control Plane 분리**: 실제 트래픽을 처리하는 Gateway(Data Plane)와 설정을 관리하는 Admin API(Control Plane)가 완벽히 분리되어 있습니다.
* **Redis Pub/Sub**: 관리자가 라우트(경로) 규칙이나 플러그인을 변경하면, Redis를 통해 모든 게이트웨이 노드에 설정이 **실시간(0.1초 이내)으로 동기화**되며 재시작 없이 즉시 반영됩니다.

### 3. 강력한 플러그인 생태계 (Middleware Plugins)
모든 라우트에 개별적으로 또는 전체(Global)에 적용할 수 있는 다양한 미들웨어 플러그인을 제공합니다.
* **Rate Limiting (트래픽 제한)**: 특정 IP나 사용자가 짧은 시간에 너무 많은 요청을 보내는 것을 차단하여 서버를 보호합니다.
* **Circuit Breaker (서킷 브레이커)**: 백엔드 서버가 다운되었을 때 연쇄 장애를 막기 위해 일시적으로 요청을 차단하고 빠르게 에러를 반환합니다.
* **보안 및 인증**: API Key, JWT 토큰 검증, mTLS(상호 인증)를 지원하여 승인된 사용자만 접근할 수 있도록 통제합니다.
* **Observability (관측성)**: 모든 요청을 추적(OpenTelemetry)하고 분석할 수 있는 상세한 로그와 프로메테우스(Prometheus) 메트릭을 제공합니다.

---

## 🛠 시작하기 (Quick Start)

초보자도 따라 할 수 있는 로컬(내 PC) 실행 가이드입니다. 

### 1. 필수 조건
* **Python 3.11 이상** 설치
* **Docker 및 Docker Compose** 설치 (Redis 및 백엔드 테스트 서버 실행용)

### 2. 환경 준비 및 의존성 설치
프로젝트 폴더로 이동한 후, Python 가상 환경을 만들고 필요한 패키지들을 설치합니다.

```bash
# 가상 환경 생성 (격리된 Python 환경을 만듭니다)
python -m venv .venv

# 가상 환경 활성화 (Mac/Linux)
source .venv/bin/activate
# Windows의 경우: .venv\Scripts\activate

# 의존성 패키지 설치
pip install -r requirements.txt
```

### 3. 전체 인프라 로컬 실행 (가장 쉬운 방법)
프로젝트에 포함된 스크립트를 사용하면 API Gateway, Admin API 서버, 그리고 필수 인프라인 Redis 인스턴스까지 모두 한 번에 실행됩니다.

```bash
# Docker Compose를 이용해 모든 서비스를 백그라운드에서 실행합니다.
./scripts/local-up.sh
```
> **참고**: 실행을 멈추고 컨테이너를 삭제하려면 `./scripts/local-down.sh`를 입력하세요.

### 4. 접속 엔드포인트 확인
서비스가 정상적으로 실행되었다면 다음 주소들로 접속할 수 있습니다.

* **Gateway (Data Plane)**: `http://localhost:8080` (클라이언트가 실제 API를 호출하는 주소)
* **Admin API (Control Plane)**: `http://localhost:9000` (관리자가 라우트 설정을 변경하는 주소)
* **Admin UI 대시보드**: `http://localhost:9000/ui` (웹 브라우저로 접속 가능한 관리자 화면)
* **메트릭(Metrics) 엔드포인트**: `http://localhost:8080/metrics` (프로메테우스 등에서 수집하는 상태 지표)

---

## 📚 상세 문서 바로가기

시스템에 대해 더 깊이 알고 싶거나 특정 작업을 수행하려면 아래의 상세 문서를 확인하세요.

| 문서 이름 | 내용 및 목적 | 추천 대상 |
|----------|------------|----------|
| [🏗 아키텍처 설계서](docs/architecture.md) | OAG의 내부 동작 원리, Data Plane / Control Plane 구조, 기술 스택 설명 | 아키텍트, 코어 개발자 |
| [🔌 연동 규격서](docs/api_spec.md) | 라우팅 규칙 스펙, Admin API 엔드포인트 목록, 플러그인 파라미터 상세 | 백엔드 연동 개발자 |
| [🛡 운영자 매뉴얼](docs/operations_runbook.md) | Kubernetes 배포, 모니터링, Admin 인증 키 발급 및 트러블슈팅 가이드 | 시스템 엔지니어, DevOps |
| [📝 사용자 매뉴얼](docs/user_guide.md) | 새로운 라우트(API 경로)를 게이트웨이에 등록하고 보안을 적용하는 튜토리얼 | 프론트/백엔드 개발자 |

---

## 🤝 기여하기 (Contributing)
이 프로젝트는 테스트 코드를 강력하게 권장합니다. 코드를 수정하신 후에는 반드시 아래 명령어로 테스트를 통과하는지 확인해 주세요.
```bash
# pytest를 이용한 전체 단위 테스트 실행
pytest tests/ -v
```
