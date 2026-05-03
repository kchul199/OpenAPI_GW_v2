# 📝 사용자 가이드 (User Guide)

이 문서는 개발자가 게이트웨이에 새로운 API를 등록하고, 보호(인증/트래픽 제한)하는 방법을 설명하는 **실무 튜토리얼**입니다.

## 🎯 목표: 나의 백엔드 API를 게이트웨이에 연결하기

여러분이 `user-service`라는 백엔드 마이크로서비스를 새로 만들었다고 가정해 봅시다. 이 서비스는 내부 포트 `8000`으로 띄워져 있고, 외부 사용자들이 `http://gateway:8080/api/users`를 통해 접근할 수 있게 만들고 싶습니다.

---

### 단계 1. 라우트 스펙 준비하기

먼저 어떤 경로의 트래픽을 어디로 보낼지 정의하는 JSON 파일을 만듭니다. `my-route.json`이라는 파일을 열고 아래 내용을 작성합니다.

```json
{
  "id": "my-user-service",
  "description": "사용자 정보 조회 및 가입 API",
  "match": {
    "protocol": "http",
    "path": "/api/users/**",
    "methods": ["GET", "POST"]
  },
  "upstream": {
    "type": "http",
    "targets": [
      {
        "url": "http://user-service:8000",
        "weight": 1
      }
    ]
  },
  "strip_prefix": false,
  "plugins": []
}
```

* **설명**: 
  * `path: "/api/users/**"`: `/api/users/profile`, `/api/users/login` 등 하위 경로를 모두 잡아냅니다.
  * `targets.url`: 게이트웨이가 트래픽을 전달할 진짜 백엔드 주소입니다.

---

### 단계 2. Admin API를 통해 라우트 등록하기

이제 작성한 JSON을 게이트웨이의 Control Plane(Admin API)에 던져줍니다. 터미널에서 다음 명령어를 실행하세요. (키값은 시스템 관리자에게 부여받은 값을 사용하세요.)

```bash
curl -X POST http://localhost:9000/api/v1/routes \
     -H "X-Admin-Key: your-admin-key" \
     -H "Content-Type: application/json" \
     -d @my-route.json
```

**✅ 성공 응답**:
```json
{
  "status": "created",
  "route": {
    "id": "my-user-service",
    ...
  }
}
```

*성공 응답을 받았다면, 게이트웨이를 재시작할 필요 없이 지금 당장 0.1초 만에 설정이 반영되었습니다!*

---

### 단계 3. 연동 테스트하기

웹 브라우저나 Postman을 열어 게이트웨이 주소로 테스트해 봅니다.
* **호출**: `http://localhost:8080/api/users/profile`
* 게이트웨이가 이 요청을 받아 `http://user-service:8000/api/users/profile`로 무사히 전달할 것입니다.

---

## 🔒 고급 활용: 플러그인(보안 및 제한) 추가하기

API가 외부에 노출되었으니, 나쁜 사용자가 초당 수천 번의 요청을 보내 서버를 죽이는 것을 막아봅시다. 아까 등록한 라우트에 **Rate Limiting(트래픽 제한)** 플러그인을 달아보겠습니다.

### 트래픽 제한 플러그인이 추가된 JSON

`update-route.json`을 새로 작성합니다. (아까 작성한 내용의 `plugins` 배열만 채워 넣으면 됩니다.)

```json
{
  "id": "my-user-service",
  "description": "사용자 정보 조회 및 가입 API (제한됨)",
  "match": {
    "protocol": "http",
    "path": "/api/users/**"
  },
  "upstream": {
    "type": "http",
    "targets": [{"url": "http://user-service:8000"}]
  },
  "plugins": [
    {
      "name": "rate-limiter",
      "enabled": true,
      "config": {
        "limit": 10,        // 최대 10번까지만 허용
        "window": 60,       // 60초(1분) 동안
        "key_func": "ip"    // IP 주소를 기준으로 제한
      }
    }
  ]
}
```

### 업데이트 API 호출

이미 있는 `my-user-service` 라우트를 수정하는 것이므로 `PUT` 메서드를 사용합니다.

```bash
curl -X PUT http://localhost:9000/api/v1/routes/my-user-service \
     -H "X-Admin-Key: your-admin-key" \
     -H "Content-Type: application/json" \
     -d @update-route.json
```

이제 특정 IP에서 1분에 10번을 초과하여 API를 호출하면, 백엔드까지 가지도 못하고 게이트웨이가 즉시 `429 Too Many Requests` 에러를 반환하며 서버를 보호해 줍니다. 

> **💡 팁**: 이외에도 `api_spec.md` 문서를 참고하여 `jwt-validator` 등 여러 플러그인을 배열에 추가하기만 하면 다양한 기능을 손쉽게 붙일 수 있습니다.
