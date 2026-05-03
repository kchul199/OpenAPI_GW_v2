# 🏗 아키텍처 설계서 (Architecture Design)

## 1. 시스템 계층 구조
본 시스템은 **Data Plane**과 **Control Plane**이 분리된 현대적인 구조를 가집니다.

### 1.1 Data Plane (Gateway)
- **역할**: 실제 클라이언트의 트래픽을 받아 인증, 제어 후 백엔드로 전달.
- **핵심 기술**: FastAPI (ASGI), `httpx` (Async Client), `grpc.aio`.
- **특징**: Stateless 구조로 자유로운 수평 확장(Scaling) 가능.

### 1.2 Control Plane (Admin)
- **역할**: 라우팅 규칙 및 보안 정책 관리, 실시간 설정 전파.
- **핵심 기술**: Redis Pub/Sub, Redis Central Store.
- **특징**: 설정 변경 시 모든 Gateway 노드에 즉각적인 핫-리로드 명령 전송.

## 2. 설정 중앙화 및 동기화 흐름
1. **관리자**: Admin API를 통해 라우트 수정.
2. **저장**: Admin 서버가 로컬 파일 저장 후 **Redis Hash**(`oag:config:routes`)에 동기화.
3. **전파**: Redis Pub/Sub 채널로 `reload` 메시지 발행.
4. **수신**: 모든 Gateway 파드가 메시지를 받고 Redis에서 최신 설정을 로드하여 메모리에 반영.

## 3. 보안 모델 (Secret Management)
- **중앙화된 시크릿**: `${JWT_SECRET}`과 같은 변수는 런타임에 치환됩니다.
- **우선순위**:
  1. `K8s Secret`: `/var/run/secrets/oag/` 경로의 파일 (가장 안전)
  2. `Environment`: 시스템 환경변수
  3. `Default`: 설정 파일 내 기본값
