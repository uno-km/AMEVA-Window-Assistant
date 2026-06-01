# AMEVA Test Harness — Manual Test Scenarios

## 시나리오 1: 정상 기본 흐름 (텍스트 채팅)
1. `python run.py` 로 앱 실행
2. 기본 세션이 자동 생성되어 있는지 확인
3. 텍스트 입력창에 "테스트 메시지" 입력 → Send 클릭
4. 상태바에 "추론중입니다..." 애니메이션 표시 확인
5. 응답이 채팅창에 표시되는지 확인
6. DB에 `tb_message` 레코드 2개 (user + assistant) 확인
7. `tb_job` 상태가 `done`인지 확인

## 시나리오 2: 서버가 꺼져 있음
1. llama.cpp 서버가 꺼진 상태에서 앱 실행
2. 메시지 전송
3. 에러 메시지가 채팅창에 빨간색으로 표시되는지 확인
4. `tb_log`에 stage=`llm` 에러 기록 확인
5. 앱이 계속 정상 동작하는지 확인 (freeze 없음)

## 시나리오 3: 추론 중 추가 요청
1. 첫 번째 메시지 전송 (서버 지연 설정: `MOCK_DELAY=5`)
2. 추론 중 두 번째 메시지 입력 → Send
3. Queue 카운트가 증가하는지 확인
4. 첫 번째 완료 후 두 번째가 자동 처리되는지 확인
5. 순서 보장 확인

## 시나리오 4: 마이크 음성 입력 (Mode B)
1. 🎙 마이크 버튼 클릭
2. 버튼이 빨간색(⏹)으로 변하는지 확인
3. 상태바에 "🔴 녹음 중..." 표시 확인
4. 다시 클릭하여 녹음 종료
5. STT 변환 텍스트가 입력창에 삽입되는지 확인
6. 자동 전송이 안 되고 Send 대기 상태인지 확인
7. Send 클릭 후 `tb_job.inp_mode = 'voice'` 확인

## 시나리오 5: TTS OFF/ON 비교
1. TTS 체크박스 OFF → 메시지 전송 → 음성 출력 없음 확인
2. TTS 체크박스 ON → 메시지 전송 → 음성 출력 확인
3. `tb_message.tts_enbl` 값 확인

## 시나리오 6: 세션 복구
1. 세션 A, B 생성 후 각각 메시지 입력
2. 앱 종료
3. 재실행 후 세션 목록에 A, B가 있는지 확인
4. 각 세션 클릭 시 해당 대화 내용이 복원되는지 확인

## 시나리오 7: 설정 변경 및 즉시 적용
1. Settings 버튼 클릭
2. LLM base_url 변경 → 저장
3. 다음 메시지부터 변경된 URL로 요청이 가는지 확인
4. 앱 재실행 후 변경된 설정이 유지되는지 확인

## 시나리오 8: Mock LLM 서버 테스트
```powershell
# 정상 모드
python tests_harness/mock_llm_server.py --port 8080

# 지연 모드 (5초)
$env:MOCK_DELAY=5; python tests_harness/mock_llm_server.py --port 8080

# 에러 모드 (HTTP 500)
$env:MOCK_ERROR=500; python tests_harness/mock_llm_server.py --port 8080

# 잘못된 JSON 모드
$env:MOCK_MALFORMED=1; python tests_harness/mock_llm_server.py --port 8080
```
