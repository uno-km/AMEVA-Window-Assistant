# AMEVA Voice Screen Assistant

AMEVA(AI Multimedia & Environment Voice Assistant)는 사용자의 화면을 분석하고, 음성 인터페이스로 대화할 수 있는 강력한 Windows 데스크탑 인공지능 어시스턴트입니다.

## 주요 기능 (Features)

*   **실시간 화면 분석 (VLM + OCR)**:
    *   사용자의 다중 모니터 화면을 인식하여, 맥락에 맞는 시각적 분석(VLM)과 텍스트 정보(OCR)를 추출합니다.
    *   자체 인텐트 라우터 모델(`qwen2.5`)이 질문의 의도를 파악하여, 화면 전체 맥락 파악(VLM)이 필요한지 텍스트 파악(OCR)이 필요한지 자동으로 분기합니다.
*   **음성 인식 (STT)**:
    *   `whisper.cpp` 엔진을 사용하여 오프라인에서 매우 빠르고 정확한 한국어/영어 음성 인식을 지원합니다.
    *   실시간 마이크 입력(ON 모드) 및 오디오 저장 히스토리 기능을 지원합니다.
*   **자동 대화 모드 (ALL 모드)**:
    *   사용자의 음성을 듣고 답변 후, 다시 음성 입력을 대기하는 완전한 핸즈프리 형태의 대화를 지원합니다 (마이크 버튼 우클릭).
    *   사일런스(침묵) 감지 기능이 내장되어 있어, 일정 시간 동안 말이 없으면 자동으로 STT 변환을 시도합니다.
*   **음성 출력 (TTS)**:
    *   Windows 기본 SAPI(PowerShell 기반)를 활용하여 자연스럽게 글을 읽어주며, 출력 스피커를 선택할 수 있습니다.
*   **로컬 호스팅 및 Docker-Compose 연동**:
    *   무거운 LLM 및 VLM 모델은 Docker 컨테이너 내에서 백그라운드로 안전하게 격리되어 실행됩니다.
    *   앱 실행 시 자동으로 컨테이너 상태를 점검하여, 필요시 `docker compose up`을 수행합니다.

## 시스템 요구사항 (Prerequisites)

1.  **Windows OS** (PowerShell, SAPI 기본 내장)
2.  **Python 3.10+**
3.  **Docker Desktop** (로컬 LLM/VLM 구동용)
4.  **Tesseract OCR** (설치 및 시스템 PATH 등록 필요)

## 설치 및 실행 (Installation)

1.  **저장소 클론**:
    ```bash
    git clone <repository_url>
    cd AMEVA-Window-Assistant
    ```

2.  **의존성 패키지 설치**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **실행**:
    ```bash
    python run.py
    # 또는
    .\run.ps1
    ```

## STT(마이크) 상세 설정 가이드

### 16kHz 리샘플링 및 FFmpeg 관련 안내
AMEVA는 실시간으로 마이크에서 입력을 받을 때, 파이썬 라이브러리(`sounddevice`)를 통해 **처음부터 16,000Hz(16kHz), 16-bit PCM 포맷으로 오디오를 캡처**합니다. 따라서:
*   별도의 **FFmpeg 전처리나 외부 리샘플링 작업이 필요하지 않습니다.**
*   `whisper.cpp`가 요구하는 최적의 포맷을 마이크에서 바로 캡처하므로 실시간 성능이 가장 우수합니다.
*   녹음된 히스토리 파일은 `data/audio/` 폴더에 타임스탬프와 함께 보관됩니다.

### Whisper.cpp 바이너리 및 모델 설정
1. 우측 상단 톱니바퀴 ⚙️ (설정) 아이콘을 클릭합니다.
2. **[음성]** 탭으로 이동합니다.
3. `Whisper 실행파일`에 `main.exe` 파일의 절대 경로를 입력합니다. (예: `C:\ameva\AI_Models\whisper.cpp\main.exe`)
4. `STT 모델` 경로에 ggml 모델이 있는 폴더(예: `C:\ameva\AI_Models\ggml`)를 지정한 후, 드롭다운에서 `.bin` 파일을 선택합니다.
5. 저장 후, 채팅창 우측의 마이크 아이콘을 통해 사용할 수 있습니다. (좌클릭: ON 모드 / 우클릭: ALL 모드)

## 폴더 구조
*   `src/`: 애플리케이션 코어 소스코드 (UI, Worker, VLM, STT 래퍼 등)
*   `db/`: SQLite 데이터베이스 저장소 (`ameva_assistant.db`)
*   `data/captures/`: 자동/수동 화면 캡처 이미지 저장소
*   `data/audio/`: 마이크 녹음(WAV) 저장소
*   `logs/`: 애플리케이션 로깅 디렉토리
*   `docker/`: LLM 및 VLM 호스팅을 위한 Docker Compose 설정
