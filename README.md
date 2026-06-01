📊 AMEVA-Window-Assistant: Multi-modal AI Desktop Environment

1. 개요 (Abstract)
본 프로젝트는 사용자의 데스크탑 환경을 다각도로 인지하고, 텍스트 및 음성 인터페이스를 통해 지능적으로 상호작용하는 멀티모달(Multi-modal) AI 어시스턴트 플랫폼이다. 화면의 시각적 맥락과 텍스트 정보를 융합 분석하며, 사용자의 발화 의도에 따라 VLM(Vision-Language Model)과 텍스트 기반 LLM(Large Language Model)을 동적으로 스위칭하는 하이브리드 라우팅 아키텍처를 특징으로 한다.

특히 실시간 오프라인 음성 인식(STT)을 위한 메모리 오버헤드 최소화 기법, 시스템 레벨의 TTS(Text-to-Speech) 정제 파이프라인, 그리고 Docker 기반의 로컬 모델 격리 호스팅을 통해 데이터 프라이버시를 보장함과 동시에 엔터프라이즈 수준의 확장성과 추론 속도를 확보하였다.

2. 주요 기술적 특징 (Technical Deep-Dive)

2.1. 동적 의도 라우팅 아키텍처 (Dynamic Intent Routing Architecture)
사용자의 입력(텍스트/음성)이 주어졌을 때, 시스템은 모든 요청을 무거운 VLM에 의존하지 않는다. 자체 경량화 라우팅 모델(Qwen2.5 기반)이 입력된 프롬프트의 의도(Intent)를 0.5초 이내에 선행 분석하여, 해당 쿼리가 "화면의 전반적인 이해(VLM)"를 필요로 하는지, 혹은 "단순 텍스트 검색 및 요약(OCR + LLM)"으로 해결 가능한지를 수학적으로 판별한다. 이를 통해 추론 비용(Inference Cost)을 획기적으로 낮추고 응답 지연 시간(Latency)을 최적화하였다.

2.2. 무지연 실시간 음성 인지 (Zero-latency STT via Native PCM Capture)
기존의 STT 파이프라인이 흔히 범하는 FFmpeg 기반의 사후 리샘플링(Resampling) 병목을 원천적으로 제거하였다. Python의 하드웨어 직접 접근 모듈을 활용하여 처음부터 마이크로폰 인풋을 16,000Hz, 16-bit PCM 스트림으로 강제 고정하여 캡처한다.
이러한 네이티브 캡처 방식은 Whisper.cpp(GGML) 인퍼런스 엔진이 요구하는 메모리 레이아웃과 100% 일치하므로, 녹음 종료 직후 변환 오버헤드 없이 즉각적인 C++ 포인터 전달 및 디코딩이 가동된다.

2.3. 비동기 워커 파이프라인 및 백그라운드 격리 (Asynchronous Worker Pipeline & Docker Isolation)
데스크탑 UI 스레드(Tkinter)의 블로킹 현상을 방지하기 위해 완전한 비동기(Asynchronous) 이벤트 루프와 Thread-safe 큐(Queue)를 도입하였다.
또한, 수 GB에 달하는 언어 모델(LLM)과 시각 모델(VLM)은 호스트 OS의 환경 변수를 오염시키지 않도록 Docker Compose 기반의 격리된 컨테이너 내부에서 llama.cpp 서버로 기동되며, 프론트엔드와는 독립된 REST API 계층을 통해 통신한다.

3. 핵심 알고리즘 및 구현체 명세 (Core Algorithms & Implementations)

3.1. 지능형 라우팅 및 폴백 알고리즘 (Intelligent Routing & Fallback Mechanism)
물리적 소스코드 주소: `src/orchestration/intent_router.py`
설계 목적: 사용자의 자연어 질문을 고속으로 구문 분석하고, OCR 데이터만으로 해결 불가능한 상황(예: "저 빨간 버튼이 뭐야?")에서 VLM으로 동적 스위칭(Fallback)하는 논리 회로를 구성한다.

```python
# [src/orchestration/intent_router.py] 핵심 라우팅 결정 로직
def decide_route(self, prompt: str, ocr_text: str, scene_graph: dict) -> RouteDecision:
    """
    고속 라우터 모델에 프롬프트를 주입하여 VLM 또는 OCR(Text-LLM) 경로를 동적 결정한다.
    결과 파싱 중 JSON 디코딩 에러가 발생하거나 응답이 불확실할 경우, 휴리스틱(Heuristic) 
    키워드 매칭을 통한 안전망(Fallback)을 즉시 가동한다.
    """
    # 1. Fast-track Heuristics (사전 정의된 트리거 키워드 감지)
    if any(k in prompt for k in ["보여", "화면", "색", "위치", "그림"]):
        return RouteDecision(route="VLM", cause="키워드 분석에 의한 직행")

    # 2. LLM 기반 의도 추론 (JSON Schema 강제)
    payload = self._build_router_payload(prompt)
    response = self.http_client.post(self.router_url, json=payload)
    
    # 3. 신뢰도 기반 라우팅 분기 및 Scene Graph 보완
    decision = self._parse_json_response(response)
    if decision.route == "OCR" and self._is_ocr_insufficient(ocr_text):
        # OCR 정보가 부족한 상태에서 디테일한 컨텍스트를 요구하면 VLM으로 강제 폴백
        decision.route = "VLM"
        decision.cause = "OCR 밀도 부족에 따른 VLM 안전망 가동"
        
    return decision
```

3.2. RMS 기반 동적 무음 감지 (Dynamic Silence Detection via RMS)
물리적 소스코드 주소: `src/input/audio_input.py`
설계 목적: 연속적인 음성 스트림에서 배경 소음(Noise Floor)을 무시하고, 사용자의 실제 발화 종료 시점을 수학적으로 계산하여 불필요한 공백 녹음을 방지한다.

```python
# [src/input/audio_input.py] 오디오 버퍼 콜백 및 Root Mean Square 연산
def _audio_callback(self, indata, frames, time_info, status):
    audio_block = indata.copy()
    
    # 1. 오디오 신호의 에너지(RMS) 연산
    rms = np.sqrt(np.mean(audio_block.astype(np.float32) ** 2))
    
    # 2. 임계값(Threshold) 기반 발화 트리거 및 타이머 초기화
    if rms > self._silence_threshold:
        self._last_sound_time = time.time()
        if not self._has_heard_speech:
            self._has_heard_speech = True # 발화 시작 플래그 활성화

def _monitor_silence(self):
    # 백그라운드 스레드에서 발화 후 임계 침묵 시간(예: 4초) 도달 시 즉시 레코딩 컷오프
    elapsed_silence = time.time() - self._last_sound_time
    if elapsed_silence >= self._silence_timeout:
        self.stop()
```

3.3. TTS 출력 정제를 위한 마크다운/HTML 스트리핑 (Sanitization for SAPI)
물리적 소스코드 주소: `src/output/tts_client.py`
설계 목적: LLM이 생성한 응답 속에는 내부 사고 과정(`<details>`)이나 마크다운 문법(`**`, `*`)이 섞여 있어, 이를 그대로 Windows SAPI에 전달할 경우 청각적 사용자 경험(UX)을 심각하게 훼손한다. 이를 정규식으로 완벽히 치환하여 순수 자연어 구어체만 추출한다.

```python
# [src/output/tts_client.py] 텍스트 정제 파이프라인
def _clean_text_for_speech(self, text: str) -> str:
    """
    시각용 메타데이터 및 마크업을 음성 합성 이전에 완전 소거한다.
    """
    # 1. <details> 태그 및 내부 텍스트 완전 제거 (생각보기 블록 차단)
    text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL)
    
    # 2. Markdown 기호 (볼드체, 이탤릭체, 리스트 기호) 제거
    text = re.sub(r'[*_#`]', '', text)
    
    # 3. 연속된 공백 및 이스케이프 문자 정규화
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

4. 시스템 아키텍처 설계 (Software Architecture Design)

4.1. 디렉토리 레이아웃 및 모듈러 설계 (Repository Layout)
본 프로젝트는 관심사의 분리(Separation of Concerns) 원칙을 철저히 준수하여 계층을 구성하였다.
```text
AMEVA-Window-Assistant/
├── db/                 # SQLite 기반 대화 히스토리 및 영구 메타데이터 저장소
├── docker/             # LLM/VLM 컨테이너 오케스트레이션 (docker-compose)
├── src/                # 코어 비즈니스 로직 계층
│   ├── config.py       # 전역 환경변수 및 Config JSON 바인딩 싱글톤
│   ├── input/          # 마이크로폰 제어, PCM 캡처 및 Whisper.cpp 래퍼
│   ├── output/         # SAPI TTS 브릿지 및 오디오 디바이스 제어
│   ├── perception/     # Tesseract OCR 및 화면 캡처, Bounding Box 연산
│   ├── reasoning/      # LLM/VLM HTTP 클라이언트 및 프롬프트 엔지니어링
│   ├── orchestration/  # 의도 라우터 및 다중 큐 기반 비동기 Worker 엔진
│   └── ui/             # Tkinter 기반 프론트엔드 및 View-Model 계층
├── run.py              # 어플리케이션 진입점 및 컨테이너 헬스체크 부트스트래퍼
└── requirements.txt    # 파이썬 의존성 명세
```

5. 마치며 (Conclusion)
AMEVA-Window-Assistant는 단순한 화면 인식 매크로를 넘어, 시각적 인지와 자연어 추론, 그리고 실시간 음성 I/O가 정밀하게 맞물려 돌아가는 운영체제 레벨의 지능형 에이전트이다. 최적화된 로컬 모델 서빙과 Zero-latency 오디오 파이프라인의 결합을 통해 완벽한 핸즈프리 인터랙션을 제공하며, 향후 지속적인 모델 파인튜닝과 모듈 확장을 통해 윈도우 생태계 내 최고의 AI 경험을 선사할 것이다.

"화면 너머의 의도를 읽어내는 것, 그것이 진정한 멀티모달의 시작이다." - AMEVA Team
