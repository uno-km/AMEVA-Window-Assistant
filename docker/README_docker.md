# llama.cpp Docker 설정 가이드

## 사전 준비

1. Docker Desktop이 설치되어 있어야 합니다.
2. GGUF 모델 파일을 `C:\ameva\models\` 디렉토리에 배치합니다. (docker-compose가 이 경로를 /models로 마운트합니다)

## 실행 방법

```powershell
cd docker

# docker-compose.yml에서 모델 파일명 수정 후 실행
docker compose up -d

# 상태 확인
docker compose ps

# 로그 보기
docker compose logs -f

# 중지
docker compose down
```

## Health Check

```powershell
# 서버 상태 확인
curl http://127.0.0.1:8080/v1/models

# 테스트 요청
curl -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"local-gguf","messages":[{"role":"user","content":"Hello"}]}'
```

## 참고 자료

- [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp Docker 가이드](https://lindevs.com/install-llama-cpp-server-inside-docker-container-on-linux)
