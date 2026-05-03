# 🏗 아키텍처 설계서 (Architecture Design)

본 문서는 **Open API Gateway(OAG) v2**의 시스템 구조, 핵심 컴포넌트, 그리고 데이터의 흐름을 초보자도 이해할 수 있도록 상세히 설명합니다.

---

## 1. 시스템 핵심 철학: 제어 평면과 데이터 평면의 분리
OAG는 현대적인 클라우드 네이티브 설계 패턴인 **Control Plane(제어 평면)**과 **Data Plane(데이터 평면)**의 분리 원칙을 따릅니다. 이는 장애 격리성과 확장성을 극대화하기 위함입니다.

```mermaid
graph TD
    subgraph Data Plane [Gateway (Data Plane)]
        HTTP[HTTP/REST Listener]
        WS[WebSocket Listener]
        GRPC[gRPC Listener]
        Router[Routing Engine]
        Middle[Middleware Pipeline]
    end

    subgraph Control Plane [Admin API (Control Plane)]
        AdminUI[Admin UI / Dashboard]
        AdminAPI[REST API]
        Audit[Audit Logger]
        RBAC[Key / Role Store]
    end

    subgraph Central Store
        Redis[(Redis)]
    end

    Client([Client Apps]) --> HTTP
    Client --> WS
    Client --> GRPC
    
    HTTP --> Router
    WS --> Router
    GRPC --> Router
    
    Router --> Middle
    Middle --> Backend[(Backend Microservices)]
    
    AdminUI --> AdminAPI
    AdminAPI -- 1. 설정 저장 --> Redis
    AdminAPI -- 2. Pub/Sub 이벤트 --> Redis
    
    Redis -. 3. 핫 리로드 알림 .-> Data Plane
```

### 1.1 Data Plane (Gateway)
* **역할**: 클라이언트로부터 들어오는 실제 트래픽을 처리하는 공장 노동자와 같습니다.
* **특징**: `State-less(무상태)`로 설계되어 있어, 트래픽이 몰리면 쿠버네티스(Kubernetes) 등에서 단순히 파드(Pod) 개수를 늘리는 것만으로 성능 확장이 가능합니다.
* **기술 스택**: `FastAPI` 기반으로 비동기 I/O를 활용하며, `httpx`를 통해 백엔드와 통신합니다. 포트 `8080`(HTTP/WS)과 `9090`(gRPC)을 주로 사용합니다.

### 1.2 Control Plane (Admin)
* **역할**: 전체 공장의 관리자 역할을 합니다. 게이트웨이의 동작 규칙(라우팅)을 변경하거나, API 키를 발급하고, 관리자들의 작업 내역(Audit)을 기록합니다.
* **특징**: 이 서버가 잠시 죽더라도 Data Plane은 이미 메모리에 올라간 규칙대로 계속 트래픽을 처리하므로 전체 서비스 장애로 이어지지 않습니다.
* **기술 스택**: 마찬가지로 `FastAPI`로 작성되었으며 포트 `9000`을 사용합니다.

---

## 2. 동적 설정 동기화 메커니즘 (Hot-Reload)

게이트웨이를 재시작하지 않고도 새로운 API 경로를 추가하거나 뺄 수 있는(Hot-Reload) 원리는 다음과 같습니다.

1. **설정 변경 요청**: 관리자가 Admin API에 새로운 라우트를 추가하는 API(`POST /api/v1/routes`)를 호출합니다.
2. **저장**: Admin API는 이 변경 사항을 로컬 파일(`routes.yaml`)과 중앙 저장소인 **Redis**에 반영합니다.
3. **이벤트 발행 (Publish)**: Admin API가 Redis의 `oag:config_reload` 채널에 "설정이 변경되었다"는 메시지를 보냅니다.
4. **수신 및 반영 (Subscribe)**: 백그라운드에서 이 채널을 듣고 있던 모든 Gateway 파드들이 메시지를 받습니다. 즉시 Redis나 로컬 파일에서 최신 설정을 읽어들여 메모리 속 라우팅 테이블을 업데이트합니다.

---

## 3. 트래픽 처리 파이프라인 (Middleware Pipeline)

클라이언트의 요청이 게이트웨이를 거쳐 백엔드로 전달되기까지의 내부 흐름입니다.

1. **인입 (Listener)**: 사용자가 `http://gateway:8080/api/users`를 호출합니다.
2. **라우팅 (Routing Engine)**: 메모리에 저장된 규칙 중 `/api/users`에 맞는 백엔드 서버 주소(`http://user-service:80`)를 찾습니다.
3. **미들웨어 파이프라인 실행**: 요청이 백엔드로 가기 전/후로 **플러그인**들이 순서대로 실행됩니다.
   * *예시:* `RateLimitPlugin` (초당 요청 수 초과 안 했나?) -> `JwtAuthPlugin` (유효한 로그인 토큰인가?)
   * 만약 플러그인에서 검사를 통과하지 못하면(예: 토큰 만료), 즉시 클라이언트에게 에러(401 Unauthorized)를 반환하고 백엔드로는 요청을 보내지 않습니다.
4. **역방향 프록시 (Reverse Proxy)**: 모든 검사를 통과하면 게이트웨이가 클라이언트를 대신해 백엔드(`http://user-service:80`)를 호출합니다.
5. **응답**: 백엔드의 응답을 받아 다시 클라이언트에게 전달합니다.

---

## 4. 보안 아키텍처 모델

OAG는 안전한 운영을 위해 여러 겹의 보안 장치를 제공합니다.

* **Admin API 보안**: Control Plane 접근은 엄격하게 통제됩니다. 모든 요청에는 `X-Admin-Key` 헤더가 필요하며, 키마다 권한(`read` 또는 `write`)이 분리된 **RBAC(Role-Based Access Control)**가 구현되어 있습니다. 또한, 화이트리스트 IP 기반 접근 제어가 가능합니다.
* **감사 로그 (Audit Log)**: 관리자가 설정을 변경할 때마다 "누가(Actor)", "언제", "어디서(IP)", "무엇을" 변경했는지 상세히 기록되어 추후 추적이 가능합니다.
* **Data Plane 보안 플러그인**: 클라이언트의 요청은 `jwt-validator`(JWT 토큰 검사), `api-key`(발급된 API 키 검사), `mtls`(클라이언트 인증서 검사) 등의 플러그인을 통해 안전하게 보호됩니다.
