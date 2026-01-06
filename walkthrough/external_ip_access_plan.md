# 계획: 외부 IP 접근 허용

이 계획은 FastAPI 백엔드와 Django 프론트엔드 모두에서 외부 IP 접근을 허용하기 위한 단계를 설명합니다.

## 제안된 변경 사항

### [백엔드 (FastAPI)]

#### [수정] [main.py](file:///d:/SKN20-4th-5TEAM/backend/app/main.py)
- `CORSMiddleware`의 `allow_origins`를 `["*"]`로 변경하여 모든 IP/도메인에서의 요청을 허용합니다.
- **이미 완료됨**: 현재 서버가 `uvicorn --host 0.0.0.0`으로 실행 중이므로 외부 접근 준비는 되어 있습니다.

---

### [프론트엔드 (Django)]

#### [수정] [settings.py](file:///d:/SKN20-4th-5TEAM/frontend/frontend/settings.py)
- `ALLOWED_HOSTS`를 `["*"]`로 변경합니다.
- **추가 조치**: `FASTAPI_BASE_URL` 설정 시 외부에서 접근할 때도 백엔드에 연결될 수 있도록 `.env` 파일이나 환경 변수에서 `FASTAPI_HOST`를 실제 서버 IP로 설정해야 합니다.

#### [실행 방식 변경]
- Django 서버 실행 시 `python manage.py runserver 0.0.0.0:8000` 명령어를 사용하여 모든 네트워크 인터페이스에서 접근 가능하도록 해야 합니다.

## 검증 계획

### 수동 검증
- 외부 IP에서 백엔드에 접근 가능한지 확인합니다.
- 외부 IP에서 프론트엔드 웹페이지에 접속 가능한지 확인합니다.
- 서로 다른 오리진에서 접근할 때 CORS 오류가 더 이상 발생하지 않는지 확인합니다.
