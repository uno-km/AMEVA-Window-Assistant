"""
AMEVA Voice Screen Assistant — Worker Thread
=============================================
Background daemon thread that consumes jobs from a ``queue.Queue``,
runs the inference pipeline (capture → OCR → semantic → prompt → LLM → save → emit), 
and pushes results back to the UI via a result queue.
"""

import logging
import os
import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ameva.orchestration.worker")

# Sentinel object to signal the worker to shut down
_SHUTDOWN = object()


@dataclass
class Job:
    job_id: int
    session_id: str
    input_text: str
    inp_mode: str = "text"          # "text" | "voice"
    capture_path: str | None = None
    tts_enabled: bool = False
    
    # Capture spec
    capture_mode: str = "full"
    monitor_index: int = 0
    
    # Fallback tracking
    semantic_fallback_used: bool = False
    backend_retry_count: int = 0
    
    # populated after completion
    result_text: str | None = None
    error_msg: str | None = None
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class WorkerResult:
    job: Job
    success: bool
    llm_provider: str = ""
    llm_model: str = ""


class WorkerThread(threading.Thread):
    def __init__(self, job_queue, result_queue, db, cfg):
        super().__init__(daemon=True, name="ameva-worker")
        self.job_queue = job_queue
        self.result_queue = result_queue
        self.db = db
        self.cfg = cfg
        
        # Lazy init providers
        self._llm = None
        self._tts = None
        self._ocr = None
        self._semantic = None
        self._prompt_builder = None

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from src.perception.ocr.tesseract_provider import TesseractProvider
                self._ocr = TesseractProvider(self.cfg)
            except Exception as e:
                logger.warning(f"OCR provider unavailable: {e}")
        return self._ocr

    def _get_semantic(self):
        if self._semantic is None:
            from src.semantic.scene_graph_builder import SceneGraphBuilder
            self._semantic = SceneGraphBuilder(self.cfg)
        return self._semantic

    def _get_prompt_builder(self):
        if self._prompt_builder is None:
            from src.reasoning.prompt_builder import PromptBuilder
            self._prompt_builder = PromptBuilder(self.cfg, self.db)
        return self._prompt_builder

    def _get_llm(self):
        if self._llm is None:
            try:
                from src.reasoning.llm_client import LlamaCppOpenAICompat
                self._llm = LlamaCppOpenAICompat(self.cfg)
            except Exception:
                logger.warning("LLM provider unavailable, using DummyLLM")
                from src.reasoning.llm_client import DummyLLM
                self._llm = DummyLLM()
        return self._llm

    def _get_tts(self):
        if self._tts is None:
            try:
                from src.output.tts_client import WindowsSAPITTS
                self._tts = WindowsSAPITTS()
            except Exception:
                logger.warning("TTS provider unavailable", exc_info=True)
        return self._tts

    def run(self):
        logger.info("Worker thread started")
        while True:
            try:
                job = self.job_queue.get()
                if job is _SHUTDOWN:
                    logger.info("Worker received shutdown signal")
                    break

                self._process_job(job)
            except Exception:
                logger.error("Worker loop error", exc_info=True)

        logger.info("Worker thread stopped")

    def _process_job(self, job: Job):
        logger.info(f"Processing job {job.job_id} (mode={job.inp_mode})")
        self.db.update_job_state(job.job_id, "running")

        stage = "init"
        try:
            # 1. Capture
            stage = "capture"
            if job.capture_path is None and self.cfg.get("capture", "auto_capture", default=True):
                try:
                    from src.input.screen_capture import ScreenCapture
                    sc = ScreenCapture(self.cfg)
                    job.capture_path = sc.capture(mode=job.capture_mode, monitor_index=job.monitor_index)
                except Exception as e:
                    logger.warning(f"Capture failed: {e}", exc_info=True)
                    
            from src.orchestration.router import FallbackRouter
            from src.reasoning.vlm_client import VLMClient

            fast_track = FallbackRouter.should_fast_track_to_vlm(job.input_text)

            # 2. OCR Extraction
            stage = "ocr"
            ocr_data = {}
            if job.capture_path:
                ocr = self._get_ocr()
                if ocr:
                    try:
                        ocr_data = ocr.extract_text_blocks(job.capture_path)
                        job.extra["ocr_raw"] = ocr_data.get("raw_blocks", []) # before post-process
                        job.extra["ocr_cleaned"] = ocr_data.get("blocks", [])
                    except Exception as e:
                        logger.warning(f"OCR failed: {e}", exc_info=True)
            
            # 3. Semantic Normalization
            stage = "semantic"
            semantic_summary = ""
            if ocr_data:
                semantic_builder = self._get_semantic()
                scene_graph, semantic_summary = semantic_builder.build(ocr_data, job.input_text)
                # We could save scene_graph to job.extra or db here
                job.extra["scene_graph"] = scene_graph

            # Fallback checking
            ocr_fallback = False
            sg_fallback = False
            if ocr_data:
                ocr_fallback = FallbackRouter.should_fallback_based_on_ocr(ocr_data.get("blocks", []))
                if job.extra.get("scene_graph"):
                    sg_fallback = FallbackRouter.should_fallback_based_on_scene_graph(job.extra["scene_graph"])

            # Qwen Intent Routing
            from src.orchestration.intent_router import IntentRouter
            qwen_router = IntentRouter(endpoint_url=self.cfg.get("router", "endpoint", default="http://127.0.0.1:8082/v1/chat/completions"))
            route_decision, route_reason, translated_prompt = qwen_router.route(job.input_text)
            self.db.update_job_routing(job.job_id, route_decision, route_reason)

            should_fallback = False
            reasons = []
            
            if route_decision == "VLM":
                should_fallback = True
                reasons.append(f"Qwen Router: {route_reason}")
            else:
                # Even if Qwen chooses OCR, fallback if OCR is physically broken/poor
                should_fallback = (ocr_fallback or sg_fallback)
                if ocr_fallback: reasons.append("Poor OCR Quality")
                if sg_fallback: reasons.append("SG Classification Failed")
                
            llm_prov = "Unknown"

            # 4. Prompt Build
            stage = "prompt"
            pb = self._get_prompt_builder()
            messages = pb.build_messages(job.session_id, job.capture_path, semantic_summary)

            # 5. LLM Call
            stage = "llm"
            job.extra["prompt"] = messages
            
            # Helper to run VLM
            def run_vlm_fallback(fallback_reason: str):
                import os
                job.semantic_fallback_used = True
                logger.info(f"Routing job {job.job_id} to VLM. Reason: {fallback_reason} (SG supplemented: {sg_fallback})")
                
                # Image Resolution-based Routing
                use_qwen_vl = False
                if job.capture_path and os.path.exists(job.capture_path):
                    try:
                        from PIL import Image
                        with Image.open(job.capture_path) as img:
                            width, height = img.size
                            pixels = width * height
                            # If image is larger than 800x800 (640,000 pixels), use Qwen2-VL
                            if pixels > 640000:
                                use_qwen_vl = True
                    except Exception as e:
                        logger.warning(f"Failed to check image size: {e}")
                
                if use_qwen_vl:
                    logger.info("Image is large (full screen). Routing to Qwen2-VL (8083).")
                    vlm_endpoint = "http://127.0.0.1:8083/v1/chat/completions"
                else:
                    logger.info("Image is small/cropped. Routing to Moondream2 (8081).")
                    vlm_endpoint = self.cfg.get("vlm", "endpoint", default="http://127.0.0.1:8081/v1/chat/completions")
                    
                vlm = VLMClient(self.cfg, endpoint_url=vlm_endpoint)
                
                # Use translated prompt from Qwen if available
                base_prompt = translated_prompt if 'translated_prompt' in locals() and translated_prompt else job.input_text
                
                if 'semantic_summary' in locals() and semantic_summary and not use_qwen_vl:
                    # Append OCR context to ground Moondream2 and prevent hallucination on dense screens
                    # We don't need this for Qwen2-VL as it reads text perfectly on its own.
                    short_summary = semantic_summary[:800] # Limit length to save context
                    vlm_prompt = f"Context (Text found on screen):\n{short_summary}\n\nQuestion: {base_prompt}"
                else:
                    vlm_prompt = base_prompt

                while job.backend_retry_count < 3:
                    try:
                        t0 = time.perf_counter()
                        r_text = vlm.ask_image(job.capture_path, vlm_prompt)
                        
                        # Translate Moondream2 (English) response to Korean
                        if not use_qwen_vl:
                            try:
                                translator_llm = self._get_llm()
                                trans_msgs = [
                                    {"role": "system", "content": "You are a professional translator. Translate the following English text into natural Korean. Output ONLY the Korean translation without any additional comments."},
                                    {"role": "user", "content": r_text}
                                ]
                                translated_r_text = translator_llm.generate(trans_msgs)
                                if translated_r_text and translated_r_text.strip():
                                    r_text = translated_r_text.strip()
                            except Exception as ex:
                                logger.warning(f"Translation of VLM response failed: {ex}")
                                
                        job.latency_ms = int((time.perf_counter() - t0) * 1000)
                        return r_text, vlm.adapter.__class__.__name__
                    except Exception as e:
                        job.backend_retry_count += 1
                        logger.warning(f"VLM backend failed (retry {job.backend_retry_count}/3): {e}")
                        time.sleep(1)
                
                logger.error("VLM failed after 3 retries. Degraded response.")
                return '{"status": "local_vlm_unavailable", "message": "Failed to connect to local VLM"}', "FallbackFailed"

            if should_fallback and not job.semantic_fallback_used:
                reason_str = " + ".join(reasons) if reasons else "Unknown Fallback"
                response_text, llm_prov = run_vlm_fallback(reason_str)
            else:
                llm = self._get_llm()
                llm_prov = type(llm).__name__
                t0 = time.perf_counter()
                response_text = llm.generate(messages)
                job.latency_ms = int((time.perf_counter() - t0) * 1000)
                
                # Retry-based LLM failure check
                if FallbackRouter.should_fallback_based_on_llm_failure(response_text) and not job.semantic_fallback_used:
                    logger.info("Text LLM returned a failure response. Triggering VLM fallback!")
                    response_text, llm_prov = run_vlm_fallback("Text LLM Failure Response")

            job.result_text = response_text
            
            if 'route_decision' in locals() and 'route_reason' in locals():
                think_block = (
                    f"<details><summary>💡 생각보기 (Qwen Router)</summary>\n"
                    f"- 판단 경로: **{route_decision}**\n"
                    f"- 판단 근거: {route_reason}\n"
                    f"- 영문 번역: {translated_prompt if 'translated_prompt' in locals() else 'N/A'}\n"
                    f"</details>\n\n"
                )
                response_text = think_block + response_text
                
            job.extra["llm_response"] = response_text
            
            # Save artifacts for debugging
            try:
                import os, json
                art_dir = os.path.join(self.cfg.get("app", "data_dir", default="data"), "artifacts")
                os.makedirs(art_dir, exist_ok=True)
                art_file = os.path.join(art_dir, f"job_{job.job_id}_artifacts.json")
                with open(art_file, "w", encoding="utf-8") as f:
                    json.dump(job.extra, f, ensure_ascii=False, indent=2)
            except Exception as art_e:
                logger.warning(f"Failed to save artifacts: {art_e}")

            # 6. Response Save
            stage = "save"
            if llm_prov not in ["LocalMockMultimodalAdapter", "LocalLlamaCppMultimodalAdapter", "FallbackFailed"]:
                llm_mdl = self.cfg.get("llm", "model_alias", default="local-gguf")
            else:
                llm_mdl = "vlm-fallback"

            self.db.insert_message(
                sess_id=job.session_id,
                role="assistant",
                content=response_text,
                cap_path=job.capture_path,
                llm_prov=llm_prov,
                llm_mdl=llm_mdl,
                tts_enbl=job.tts_enabled,
                ltncy_ms=job.latency_ms,
            )

            # (Optional) TTS
            stage = "tts"
            if job.tts_enabled:
                tts = self._get_tts()
                if tts is not None:
                    try:
                        tts.speak(response_text)
                    except Exception as e:
                        logger.warning(f"TTS failed (non-fatal): {e}")

            # 7. UI Emit
            stage = "emit"
            self.db.update_job_state(job.job_id, "done")
            self.db.update_session_active(job.session_id)

            self.result_queue.put(
                WorkerResult(job=job, success=True, llm_provider=llm_prov, llm_model=llm_mdl)
            )
            logger.info(f"Job {job.job_id} completed ({job.latency_ms}ms)")

        except Exception as e:
            tb_str = traceback.format_exc()
            job.error_msg = f"[{stage} stage] {str(e)}"
            logger.error(f"Job {job.job_id} failed at {stage}: {e}", exc_info=True)

            err_id = self.db.insert_log(
                level="ERROR",
                message=f"[worker:{stage}] Job {job.job_id}: {e}",
                tb=tb_str,
            )
            self.db.update_job_state(job.job_id, "error", err_id=err_id)

            self.result_queue.put(WorkerResult(job=job, success=False))

    def request_shutdown(self):
        """Signal the worker to stop after finishing the current job."""
        self.job_queue.put(_SHUTDOWN)

SHUTDOWN_SENTINEL = _SHUTDOWN
