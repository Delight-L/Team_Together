# Render Docker 배포

저장소 루트의 Dockerfile은 React를 빌드한 뒤 Python 실행 환경에 화면과 필수 자료를 넣습니다.
비밀번호는 이미지에 넣지 않고 Render 환경변수로 전달합니다.

- Language: Docker
- Branch: main (이 변경이 main에 반영된 후 배포)
- Root Directory: 비움
- Dockerfile Path: ./Dockerfile
- Instance Type: Free
- Docker Command: 비움 (Dockerfile CMD 사용)
- Health Check Path: /api/health

DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SSLMODE=require,
WELFIND_DATA_SOURCE=db를 설정합니다. 앱 계정에는 work 스키마 저장 권한도 필요합니다.
HOST=0.0.0.0은 이미지에 설정되며 PORT는 Render가 제공하는 값이 적용됩니다.

로컬 확인:

```powershell
docker build -t welfind:local .
docker run --rm -p 10000:10000 --env-file .env welfind:local
```

http://localhost:10000/api/health 와 로그인·대시보드·보고서 기능을 확인합니다.
DB 업무 기록은 PostgreSQL에 저장되지만 로그인 세션·미리보기는 메모리에 있습니다.
현재 관리자 AI 설정은 backend/db/runtime/ai_settings.json에 저장되므로 무료 서비스
재시작 후 보존되지 않습니다. API 키는 Render 환경변수에 설정하고 영구 AI 설정은
별도 PostgreSQL 이전이 필요합니다.
