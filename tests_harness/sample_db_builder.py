"""
AMEVA Test Harness — Sample Database Builder
==============================================
Seeds the SQLite database with demo sessions, messages, jobs, and logs
for UI testing and demonstration purposes.

Usage::

    python tests_harness/sample_db_builder.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CFG
from src.storage.db import DatabaseManager


def build_sample_data():
    db_path = CFG.resolve_path(CFG.get("db", "path", default="db/ameva_assistant.db"))
    db = DatabaseManager(db_path)

    print(f"Building sample data in: {db_path}")

    # --- Session 1: Error debugging ---
    s1 = db.create_session("Python 에러 디버깅")
    db.insert_message(s1, "user", "이 에러 뭔지 알려줘: TypeError: 'NoneType' object is not iterable")
    db.insert_message(
        s1, "assistant",
        "이 에러는 None 값을 반복(iterate)하려고 할 때 발생합니다.\n\n"
        "예를 들어:\n```python\nfor item in some_function():\n    print(item)\n```\n"
        "여기서 `some_function()`이 `None`을 반환하면 이 에러가 발생합니다.\n\n"
        "해결 방법:\n1. 반환값이 None인지 먼저 확인\n2. 기본값을 빈 리스트로 설정",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf", ltncy_ms=1250,
    )
    db.insert_message(s1, "user", "그러면 None 체크는 어떻게 해?")
    db.insert_message(
        s1, "assistant",
        "```python\nresult = some_function()\nif result is not None:\n    for item in result:\n        print(item)\n```\n\n"
        "또는 기본값을 사용할 수 있습니다:\n```python\nfor item in (some_function() or []):\n    print(item)\n```",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf", ltncy_ms=980,
    )
    print(f"  Session 1: {s1} (4 messages)")

    # --- Session 2: 화면 분석 ---
    s2 = db.create_session("화면 캡처 분석 테스트")
    db.insert_message(s2, "user", "지금 화면에 뭐가 보이는지 설명해줘", cap_path="data/captures/sample/cap_test.png")
    db.insert_message(
        s2, "assistant",
        "현재 화면에는 코드 에디터(VS Code)가 열려 있습니다.\n"
        "Python 파일이 편집 중이며, 터미널 패널에 테스트 출력이 보입니다.",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf",
        ltncy_ms=2100, cap_path="data/captures/sample/cap_test.png",
    )
    print(f"  Session 2: {s2} (2 messages)")

    # --- Session 3: 음성 입력 테스트 ---
    s3 = db.create_session("음성 입력 테스트")
    db.insert_message(s3, "user", "안녕하세요 음성 테스트입니다", stt_prov="whisper.cpp")
    db.insert_message(
        s3, "assistant",
        "안녕하세요! 음성 입력이 잘 인식되었네요. 무엇을 도와드릴까요?",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf", ltncy_ms=750,
    )
    print(f"  Session 3: {s3} (2 messages)")

    # --- Sample jobs ---
    j1 = db.insert_job(s1, "이 에러 뭔지 알려줘", inp_mode="text")
    db.update_job_state(j1, "done")
    j2 = db.insert_job(s3, "안녕하세요 음성 테스트입니다", inp_mode="voice")
    db.update_job_state(j2, "done")

    # --- Sample logs ---
    db.insert_log(level="INFO", message="Application started")
    db.insert_log(level="WARNING", message="[stt] whisper.cpp not found — using fallback")
    db.insert_log(level="ERROR", message="[llm] Connection refused: http://127.0.0.1:8080/v1/models",
                  tb="Traceback (most recent call last):\n  ...\nConnectionError: Connection refused")

    print("\nSample data built successfully!")
    print(f"  Sessions: {len(db.list_sessions())}")


if __name__ == "__main__":
    build_sample_data()
