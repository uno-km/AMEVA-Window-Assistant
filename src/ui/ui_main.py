"""
AMEVA Voice Screen Assistant — Main Tkinter UI
================================================
Dual-panel chat interface with session list, chat log, input area,
status bar with spinner/animation, and mic button for voice input.

All long-running operations happen in the worker thread.  The UI
polls ``result_queue`` via ``after()`` and never blocks.
"""

import logging
import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from src.orchestration.worker import WorkerThread, Job, WorkerResult

logger = logging.getLogger("ameva.ui")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_POLL_MS = 100          # result queue polling interval
_ANIM_MS = 300          # spinner / dots animation interval
_SPINNER = ["|", "/", "—", "\\"]
_DOTS = ["", ".", "..", "..."]

# Color palette
_CLR_BG        = "#1e1e2e"
_CLR_BG_LIGHT  = "#2a2a3d"
_CLR_FG        = "#cdd6f4"
_CLR_USER      = "#89b4fa"
_CLR_ASST      = "#a6e3a1"
_CLR_SYSTEM    = "#6c7086"
_CLR_ERROR     = "#f38ba8"
_CLR_ACCENT    = "#cba6f7"
_CLR_ENTRY_BG  = "#313244"
_CLR_BTN       = "#45475a"
_CLR_BTN_HOVER = "#585b70"
_CLR_MIC_REC   = "#f38ba8"
_CLR_LINK      = "#74c7ec"


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------
class MainWindow(tk.Tk):
    """
    Top-level Tkinter window hosting the full assistant UI.

    Parameters
    ----------
    db : DatabaseManager
    cfg : AppConfig
    """

    def __init__(self, db, cfg):
        super().__init__()

        self.db = db
        self.cfg = cfg

        # State
        self._current_session_id: str | None = None
        self._is_running = False
        self._spinner_idx = 0
        self._dots_idx = 0
        self._recording = False
        self._draft_image_path: str | None = None
        self._draft_photo = None

        # Queues
        self._job_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()

        # Worker
        self._worker = WorkerThread(
            self._job_queue, self._result_queue, self.db, self.cfg
        )
        self._worker.start()

        # Window config
        self.title("AMEVA Voice Screen Assistant")
        self.geometry("1100x720")
        self.minsize(800, 500)
        self.configure(bg=_CLR_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Build UI
        self._build_ui()
        self._load_sessions()

        # Start polling loops
        self._poll_results()
        self._animate_status()

    # ==================================================================
    #  UI Construction
    # ==================================================================
    def _build_ui(self):
        # --- Main horizontal paned window ---
        paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, bg=_CLR_BG,
            sashwidth=3, sashrelief=tk.FLAT,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Left: Session panel
        self._left_frame = tk.Frame(paned, bg=_CLR_BG_LIGHT, width=240)
        paned.add(self._left_frame, minsize=180)
        self._build_session_panel(self._left_frame)

        # Right: Chat + Input + Status
        self._right_frame = tk.Frame(paned, bg=_CLR_BG)
        paned.add(self._right_frame, minsize=500)
        self._build_chat_panel(self._right_frame)
        self._build_input_panel(self._right_frame)
        self._build_status_bar(self._right_frame)

    # ------------------------------------------------------------------
    # Session panel (Left)
    # ------------------------------------------------------------------
    def _build_session_panel(self, parent):
        header = tk.Frame(parent, bg=_CLR_BG_LIGHT)
        header.pack(fill=tk.X, padx=8, pady=(8, 4))

        tk.Label(
            header, text="세션 목록", font=("Segoe UI", 11, "bold"),
            bg=_CLR_BG_LIGHT, fg=_CLR_ACCENT,
        ).pack(side=tk.LEFT)

        btn_new = tk.Button(
            header, text="＋ 새 세션", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER, activeforeground=_CLR_FG,
            command=self._on_new_session,
        )
        btn_new.pack(side=tk.RIGHT)

        self._session_listbox = tk.Listbox(
            parent, font=("Segoe UI", 10), bg=_CLR_BG_LIGHT,
            fg=_CLR_FG, selectbackground=_CLR_ACCENT,
            selectforeground=_CLR_BG, relief=tk.FLAT,
            activestyle="none", borderwidth=0, highlightthickness=0,
        )
        self._session_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._session_listbox.bind("<<ListboxSelect>>", self._on_session_select)

        # Internal mapping: listbox index → session id
        self._session_ids: list[str] = []

    # ------------------------------------------------------------------
    # Chat panel (Center)
    # ------------------------------------------------------------------
    def _build_chat_panel(self, parent):
        chat_frame = tk.Frame(parent, bg=_CLR_BG)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        self._chat_text = tk.Text(
            chat_frame, wrap=tk.WORD, state=tk.DISABLED,
            bg=_CLR_BG, fg=_CLR_FG, font=("Segoe UI", 10),
            relief=tk.FLAT, borderwidth=0, padx=12, pady=8,
            insertbackground=_CLR_FG, selectbackground=_CLR_ACCENT,
            cursor="arrow",
        )
        scrollbar = ttk.Scrollbar(chat_frame, command=self._chat_text.yview)
        self._chat_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tag styles
        self._chat_text.tag_configure("user", foreground=_CLR_USER, font=("Segoe UI", 10, "bold"))
        self._chat_text.tag_configure("assistant", foreground=_CLR_ASST)
        self._chat_text.tag_configure("system", foreground=_CLR_SYSTEM, font=("Segoe UI", 9, "italic"))
        self._chat_text.tag_configure("error", foreground=_CLR_ERROR)
        self._chat_text.tag_configure("meta", foreground=_CLR_SYSTEM, font=("Segoe UI", 8))
        self._chat_text.tag_configure("link", foreground=_CLR_LINK, underline=True)
        self._chat_text.tag_bind("link", "<Button-1>", self._on_link_click)
        self._chat_text.tag_bind("link", "<Enter>", lambda e: self._chat_text.configure(cursor="hand2"))
        self._chat_text.tag_bind("link", "<Leave>", lambda e: self._chat_text.configure(cursor="arrow"))

    # ------------------------------------------------------------------
    # Input panel (Bottom)
    # ------------------------------------------------------------------
    def _build_input_panel(self, parent):
        input_frame = tk.Frame(parent, bg=_CLR_BG)
        input_frame.pack(fill=tk.X, padx=8, pady=4)

        # Top row: text entry + mic button
        entry_row = tk.Frame(input_frame, bg=_CLR_ENTRY_BG)
        entry_row.pack(fill=tk.X, pady=(0, 4))
        
        # Preview row inside entry row
        self._preview_frame = tk.Frame(entry_row, bg=_CLR_ENTRY_BG)
        self._preview_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 0))
        self._lbl_preview = tk.Label(self._preview_frame, bg=_CLR_ENTRY_BG)
        self._lbl_preview.pack(side=tk.LEFT)
        self._btn_clear_preview = tk.Button(
            self._preview_frame, text="✖", font=("Segoe UI", 8),
            bg=_CLR_ENTRY_BG, fg=_CLR_ERROR, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_ENTRY_BG, command=self._clear_draft
        )
        self._preview_frame.pack_forget() # Hide by default

        self._input_text = tk.Text(
            entry_row, height=3, wrap=tk.WORD,
            bg=_CLR_ENTRY_BG, fg=_CLR_FG, font=("Segoe UI", 10),
            relief=tk.FLAT, borderwidth=8, insertbackground=_CLR_FG,
        )
        self._input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._input_text.bind("<Return>", self._on_enter_key)
        self._input_text.bind("<Shift-Return>", lambda e: None)  # allow newline

        self._mic_btn = tk.Button(
            entry_row, text="🎙", font=("Segoe UI", 14),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT,
            width=3, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_mic_click,
        )
        self._mic_btn.pack(side=tk.RIGHT, padx=(4, 4), pady=4)

        # Bottom row: buttons
        btn_row = tk.Frame(input_frame, bg=_CLR_BG)
        btn_row.pack(fill=tk.X)

        self._tts_var = tk.BooleanVar(value=self.cfg.get("tts", "enabled", default=False))
        tts_check = tk.Checkbutton(
            btn_row, text="TTS 읽기", variable=self._tts_var,
            bg=_CLR_BG, fg=_CLR_FG, selectcolor=_CLR_ENTRY_BG,
            activebackground=_CLR_BG, activeforeground=_CLR_FG,
            font=("Segoe UI", 9),
        )
        tts_check.pack(side=tk.LEFT)

        btn_send = tk.Button(
            btn_row, text="Send →", font=("Segoe UI", 10, "bold"),
            bg=_CLR_ACCENT, fg=_CLR_BG, relief=tk.FLAT,
            cursor="hand2", padx=16,
            activebackground=_CLR_BTN_HOVER,
            command=self._on_send,
        )
        btn_send.pack(side=tk.RIGHT, padx=(4, 0))
        
        # Monitor Selection Dropdown
        try:
            from src.input.screen_capture import ScreenCapture
            sc = ScreenCapture(self.cfg)
            monitors = sc.list_monitors()
            monitor_opts = ["전체 화면"]
            for m in monitors:
                monitor_opts.append(f"모니터 {m['index']}")
        except Exception:
            monitor_opts = ["전체 화면"]
            
        self._monitor_var = tk.StringVar(value=monitor_opts[0])
        self._monitor_cb = ttk.Combobox(
            btn_row, textvariable=self._monitor_var, values=monitor_opts,
            state="readonly", width=12, font=("Segoe UI", 9)
        )
        self._monitor_cb.pack(side=tk.RIGHT, padx=4)
        
        btn_identify = tk.Button(
            btn_row, text="식별", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_identify_monitors,
        )
        btn_identify.pack(side=tk.RIGHT, padx=4)

        btn_settings = tk.Button(
            btn_row, text="⚙ Settings", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_settings,
        )
        btn_settings.pack(side=tk.RIGHT, padx=4)

        btn_capture = tk.Button(
            btn_row, text="📷 Capture", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_manual_capture,
        )
        btn_capture.pack(side=tk.RIGHT, padx=4)

        btn_snip = tk.Button(
            btn_row, text="✂ 영역 지정", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_snip,
        )
        btn_snip.pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_status_bar(self, parent):
        bar = tk.Frame(parent, bg=_CLR_BG_LIGHT, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        bar.pack_propagate(False)

        self._lbl_state = tk.Label(
            bar, text="Idle", font=("Segoe UI", 9),
            bg=_CLR_BG_LIGHT, fg=_CLR_ASST, anchor="w",
        )
        self._lbl_state.pack(side=tk.LEFT, padx=8)

        self._lbl_spinner = tk.Label(
            bar, text="", font=("Consolas", 10),
            bg=_CLR_BG_LIGHT, fg=_CLR_ACCENT, width=2,
        )
        self._lbl_spinner.pack(side=tk.LEFT)

        self._lbl_queue = tk.Label(
            bar, text="Queue 0", font=("Segoe UI", 9),
            bg=_CLR_BG_LIGHT, fg=_CLR_SYSTEM,
        )
        self._lbl_queue.pack(side=tk.LEFT, padx=12)

        self._lbl_server_status = tk.Label(
            bar, text="⚫ 도커 헬스체크 대기중...", font=("Segoe UI", 9, "bold"),
            bg=_CLR_BG_LIGHT, fg=_CLR_FG, anchor="e",
        )
        self._lbl_server_status.pack(side=tk.RIGHT, padx=8)

        # Start polling
        self.after(2000, self._poll_server_status)
        self._lbl_model = tk.Label(
            bar, text=f"LLM: {self.cfg.get('llm', 'model_alias', default='—')}",
            font=("Segoe UI", 9), bg=_CLR_BG_LIGHT, fg=_CLR_SYSTEM,
        )
        self._lbl_model.pack(side=tk.RIGHT, padx=8)

    # ==================================================================
    #  Session logic
    # ==================================================================
    def _load_sessions(self):
        sessions = self.db.list_sessions()
        self._session_listbox.delete(0, tk.END)
        self._session_ids.clear()
        for s in sessions:
            self._session_listbox.insert(tk.END, f"  {s['ttl']}")
            self._session_ids.append(s["id"])
        # Auto-select first
        if sessions:
            self._session_listbox.selection_set(0)
            self._current_session_id = sessions[0]["id"]
            self._load_chat_history()

    def _on_new_session(self):
        sid = self.db.create_session()
        self._load_sessions()
        # Select the newest (first in list)
        self._session_listbox.selection_clear(0, tk.END)
        self._session_listbox.selection_set(0)
        self._current_session_id = sid
        self._load_chat_history()

    def _on_session_select(self, event):
        sel = self._session_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._current_session_id = self._session_ids[idx]
        self._load_chat_history()

    # ==================================================================
    #  Chat display
    # ==================================================================
    def _load_chat_history(self):
        """Reload chat from DB for the current session."""
        self._chat_text.configure(state=tk.NORMAL)
        self._chat_text.delete("1.0", tk.END)

        if not self._current_session_id:
            self._chat_text.configure(state=tk.DISABLED)
            return

        messages = self.db.get_messages(self._current_session_id)
        for msg in messages:
            self._render_message(msg)

        self._chat_text.configure(state=tk.DISABLED)
        self._chat_text.see(tk.END)

    def _render_message(self, msg: dict):
        """Append a single message to the chat text widget."""
        role = msg.get("role", "system")
        content = msg.get("content", "")
        ts = msg.get("create_dt", "")
        latency = msg.get("ltncy_ms")
        model = msg.get("llm_mdl", "")
        cap = msg.get("cap_path", "")

        # Role label
        if role == "user":
            label = "👤 You"
            tag = "user"
        elif role == "assistant":
            label = "🤖 Assistant"
            tag = "assistant"
        elif role == "error":
            label = "⚠ Error"
            tag = "error"
        else:
            label = "ℹ System"
            tag = "system"

        self._chat_text.insert(tk.END, f"{label}  ", tag)
        self._chat_text.insert(tk.END, f"{ts}\n", "meta")

        # Parse and render collapsible details block if present
        if role == "assistant" and "<details>" in content:
            import re
            import time
            pattern = re.compile(r"<details><summary>(.*?)</summary>(.*?)</details>(.*)", re.DOTALL)
            match = pattern.search(content)
            if match:
                summary_text = match.group(1).strip()
                details_text = match.group(2).strip()
                remaining_text = match.group(3).strip()
                
                msg_id = msg.get("id") or int(time.time() * 1000)
                details_tag = f"details_{msg_id}"
                btn_tag = f"btn_{msg_id}"
                
                # Grayish color, italic/smaller font for reasoning
                self._chat_text.tag_configure(details_tag, elide=True, foreground="#94e2d5", font=("Segoe UI", 9, "italic"))
                
                def toggle_details(e, d_tag=details_tag, b_tag=btn_tag, s_text=summary_text):
                    current_elide = self._chat_text.tag_cget(d_tag, "elide")
                    # In Tkinter, elide value can be '1', '0', True, or False
                    is_hidden = current_elide in [True, "1", 1]
                    new_elide = not is_hidden
                    self._chat_text.tag_configure(d_tag, elide=new_elide)
                    
                    btn_text = f"▼ {s_text}" if not new_elide else f"▶ {s_text}"
                    
                    ranges = self._chat_text.tag_ranges(b_tag)
                    if ranges:
                        self._chat_text.configure(state=tk.NORMAL)
                        self._chat_text.delete(ranges[0], ranges[1])
                        self._chat_text.insert(ranges[0], btn_text, (b_tag, "link"))
                        self._chat_text.configure(state=tk.DISABLED)
                
                start_btn_text = f"▶ {summary_text}"
                self._chat_text.insert(tk.END, f"{start_btn_text}\n", (btn_tag, "link"))
                
                self._chat_text.tag_bind(btn_tag, "<Button-1>", toggle_details)
                self._chat_text.tag_bind(btn_tag, "<Enter>", lambda e: self._chat_text.configure(cursor="hand2"))
                self._chat_text.tag_bind(btn_tag, "<Leave>", lambda e: self._chat_text.configure(cursor="arrow"))
                
                self._chat_text.insert(tk.END, f"{details_text}\n\n", details_tag)
                self._chat_text.insert(tk.END, f"{remaining_text}\n", tag)
            else:
                self._chat_text.insert(tk.END, f"{content}\n", tag)
        else:
            self._chat_text.insert(tk.END, f"{content}\n", tag)

        # Meta line
        meta_parts = []
        if latency:
            meta_parts.append(f"{latency}ms")
        if model:
            meta_parts.append(model)
        if cap:
            meta_parts.append(f"📎 ")
            self._chat_text.insert(tk.END, " ".join(meta_parts), "meta")
            # Store path in a tag for click handling
            link_tag = f"link_{msg.get('id', 0)}"
            self._chat_text.tag_configure(link_tag, foreground=_CLR_LINK, underline=True)
            self._chat_text.tag_bind(link_tag, "<Button-1>", lambda e, p=cap: self._open_file(p))
            self._chat_text.tag_bind(link_tag, "<Enter>", lambda e: self._chat_text.configure(cursor="hand2"))
            self._chat_text.tag_bind(link_tag, "<Leave>", lambda e: self._chat_text.configure(cursor="arrow"))
            self._chat_text.insert(tk.END, os.path.basename(cap), link_tag)
            self._chat_text.insert(tk.END, "\n", "meta")
        elif meta_parts:
            self._chat_text.insert(tk.END, " ".join(meta_parts) + "\n", "meta")

        self._chat_text.insert(tk.END, "\n")

    def _append_message_to_chat(self, msg: dict):
        """Append a single message and scroll to bottom."""
        self._chat_text.configure(state=tk.NORMAL)
        self._render_message(msg)
        self._chat_text.configure(state=tk.DISABLED)
        self._chat_text.see(tk.END)

    # ==================================================================
    #  Input handlers
    # ==================================================================
    def _on_enter_key(self, event):
        """Send on Enter (Shift+Enter for newline)."""
        self._on_send()
        return "break"

    def _on_send(self):
        """Submit the current text input as a user message."""
        text = self._input_text.get("1.0", tk.END).strip()
        if not text:
            return
        if not self._current_session_id:
            messagebox.showwarning("세션 없음", "먼저 세션을 선택하거나 새 세션을 만들어주세요.")
            return

        self._input_text.delete("1.0", tk.END)

        # Determine input mode
        inp_mode = self._pending_inp_mode if hasattr(self, "_pending_inp_mode") else "text"
        self._pending_inp_mode = "text"  # reset

        # Save user message to DB
        stt_prov = "whisper.cpp" if inp_mode == "voice" else None
        msg_id = self.db.insert_message(
            sess_id=self._current_session_id,
            role="user",
            content=text,
            stt_prov=stt_prov,
            tts_enbl=self._tts_var.get(),
        )

        # Show in chat immediately
        self._append_message_to_chat({
            "id": msg_id, "role": "user", "content": text,
            "create_dt": "", "ltncy_ms": None, "llm_mdl": None, "cap_path": None,
        })

        # Create job
        job_id = self.db.insert_job(
            sess_id=self._current_session_id,
            inp_txt=text,
            llm_prov="LlamaCppOpenAICompat",
            llm_mdl=self.cfg.get("llm", "model_alias", default=""),
            inp_mode=inp_mode,
        )

        # Parse Monitor selection
        mon_val = self._monitor_var.get()
        capture_mode = "full"
        monitor_index = 0
        if mon_val.startswith("모니터"):
            capture_mode = "monitor"
            try:
                monitor_index = int(mon_val.split()[-1]) - 1
            except:
                pass

        capture_path_override = self._draft_image_path

        # Push to worker queue
        job = Job(
            job_id=job_id,
            session_id=self._current_session_id,
            input_text=text,
            inp_mode=inp_mode,
            capture_path=capture_path_override,
            tts_enabled=self._tts_var.get(),
            capture_mode=capture_mode,
            monitor_index=monitor_index
        )
        self._job_queue.put(job)
        self._is_running = True
        self._update_status()
        self._clear_draft()

        # Auto-update session title from first message
        msgs = self.db.get_messages(self._current_session_id)
        if len(msgs) == 1:
            title = text[:40] + ("…" if len(text) > 40 else "")
            self.db.update_session_title(self._current_session_id, title)
            self._load_sessions()

    def _on_mic_click(self):
        """Toggle microphone recording state."""
        if self._recording:
            # Stop recording
            self._recording = False
            self._mic_btn.configure(bg=_CLR_BTN, text="🎙")
            self._lbl_state.configure(text="STT 변환 중...")

            # In Phase 4 this will call the actual STT provider.
            # For now, show a placeholder message.
            try:
                from src.input.audio_input import WhisperCppSTT
                stt = WhisperCppSTT(self.cfg)
                transcribed = stt.transcribe()
                if transcribed:
                    self._input_text.delete("1.0", tk.END)
                    self._input_text.insert("1.0", transcribed)
                    self._pending_inp_mode = "voice"
                self._lbl_state.configure(text="Idle")
            except Exception as e:
                logger.warning(f"STT failed: {e}")
                self._lbl_state.configure(text="STT 실패")
                self.db.insert_log(level="WARNING", message=f"[stt] {e}")
        else:
            # Start recording
            self._recording = True
            self._mic_btn.configure(bg=_CLR_MIC_REC, text="⏹")
            self._lbl_state.configure(text="🔴 녹음 중...")

    def _on_manual_capture(self):
        """Manually capture the screen."""
        try:
            from src.input.screen_capture import ScreenCapture
            sc = ScreenCapture(self.cfg)
            
            mon_val = self._monitor_var.get()
            capture_mode = "full"
            monitor_index = 0
            if mon_val.startswith("모니터"):
                capture_mode = "monitor"
                try:
                    monitor_index = int(mon_val.split()[-1]) - 1
                except:
                    pass
            
            path = sc.capture(mode=capture_mode, monitor_index=monitor_index)
            logger.info(f"Manual capture: {path}")
            messagebox.showinfo("캡처 완료", f"저장됨:\n{path}")
        except Exception as e:
            logger.error(f"Manual capture failed: {e}")
            messagebox.showerror("캡처 실패", str(e))

    def _on_identify_monitors(self):
        """Show large OSD numbers on each monitor for 2 seconds."""
        try:
            from src.input.screen_capture import ScreenCapture
            sc = ScreenCapture(self.cfg)
            monitors = sc.list_monitors()
            
            for m in monitors:
                top = tk.Toplevel(self)
                top.overrideredirect(True)
                top.attributes("-topmost", True)
                top.attributes("-alpha", 0.8)
                top.config(bg="black")
                
                # Position in center of the monitor
                w, h = 300, 300
                x = m["left"] + (m["width"] - w) // 2
                y = m["top"] + (m["height"] - h) // 2
                top.geometry(f"{w}x{h}+{x}+{y}")
                
                # Text
                lbl = tk.Label(
                    top, text=str(m["index"]), 
                    font=("Segoe UI", 120, "bold"), fg="white", bg="black"
                )
                lbl.pack(expand=True, fill=tk.BOTH)
                
                # Destroy after 2 seconds
                top.after(2000, top.destroy)
                
        except Exception as e:
            logger.error(f"Identify monitors failed: {e}")

    def _clear_draft(self):
        self._draft_image_path = None
        self._draft_photo = None
        self._preview_frame.pack_forget()

    def _on_snip(self):
        try:
            from src.ui.snipping_tool import SnippingTool
            SnippingTool(self, self._on_snip_complete)
        except Exception as e:
            logger.error(f"Snipping tool failed: {e}")
            messagebox.showerror("오류", f"스니핑 도구를 열 수 없습니다: {e}")

    def _on_snip_complete(self, img):
        import time
        from PIL import ImageTk
        from pathlib import Path
        
        # Save to captures
        capture_dir = Path("data/captures") / time.strftime("%Y%m%d")
        capture_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = capture_dir / f"cap_{ts}_snip.png"
        img.save(path)
        self._draft_image_path = str(path)
        
        # Create thumbnail
        img.thumbnail((150, 150))
        self._draft_photo = ImageTk.PhotoImage(img)
        self._lbl_preview.configure(image=self._draft_photo)
        self._btn_clear_preview.pack(side=tk.RIGHT, padx=4)
        self._preview_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 0), before=self._input_text)

    def _on_settings(self):
        """Open the settings dialog."""
        try:
            from src.ui.ui_settings import SettingsDialog
            SettingsDialog(self, self.cfg, self.db)
        except Exception as e:
            logger.error(f"Settings dialog error: {e}")
            messagebox.showerror("설정 오류", str(e))

    def _on_link_click(self, event):
        """Fallback link click handler."""
        pass

    def _open_file(self, path):
        """Open a file using the system default viewer."""
        try:
            os.startfile(path)
        except Exception as e:
            logger.warning(f"Cannot open file {path}: {e}")

    # ==================================================================
    #  Polling & Animation
    # ==================================================================
    def _poll_results(self):
        """Check for completed jobs and update UI."""
        try:
            while True:
                result: WorkerResult = self._result_queue.get_nowait()
                self._handle_result(result)
        except queue.Empty:
            pass

        # Update queue count display
        self._update_status()
        self.after(_POLL_MS, self._poll_results)

    def _handle_result(self, result: WorkerResult):
        """Process a completed job result."""
        job = result.job
        if job.session_id != self._current_session_id:
            return  # Result for a different session tab

        if result.success:
            self._append_message_to_chat({
                "id": 0, "role": "assistant",
                "content": job.result_text,
                "create_dt": "",
                "ltncy_ms": job.latency_ms,
                "llm_mdl": result.llm_model,
                "cap_path": job.capture_path,
            })
        else:
            self._append_message_to_chat({
                "id": 0, "role": "error",
                "content": f"오류 발생: {job.error_msg}",
                "create_dt": "", "ltncy_ms": None,
                "llm_mdl": None, "cap_path": None,
            })

    def _update_status(self):
        """Refresh status bar labels."""
        qc = self._job_queue.qsize()
        if qc > 0 or self._is_running:
            self._lbl_queue.configure(text=f"Queue {qc}")
        else:
            self._lbl_queue.configure(text="Queue 0")
            self._is_running = False

    def _animate_status(self):
        """Cycle spinner and dots while running."""
        if self._is_running or not self._job_queue.empty():
            self._is_running = True
            self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER)
            self._dots_idx = (self._dots_idx + 1) % len(_DOTS)
            self._lbl_spinner.configure(text=_SPINNER[self._spinner_idx])
            self._lbl_state.configure(
                text=f"추론중입니다{_DOTS[self._dots_idx]}",
                fg=_CLR_ACCENT,
            )
        else:
            self._lbl_spinner.configure(text="")
            if not self._recording:
                self._lbl_state.configure(text="Idle", fg=_CLR_ASST)

        self.after(_ANIM_MS, self._animate_status)

    def _poll_server_status(self):
        import urllib.request
        llm_url = self.cfg.get("llm", "base_url", default="http://127.0.0.1:8080/v1") + "/models"
        vlm_url = "http://127.0.0.1:8081/v1/models"
        
        def check_url(url):
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    return resp.status == 200
            except Exception:
                return False
                
        llm_ok = check_url(llm_url)
        vlm_ok = check_url(vlm_url)
        
        if llm_ok and vlm_ok:
            self._lbl_server_status.configure(text="🔵 도커 서버(LLM+VLM) 온라인", fg="#89b4fa")
        elif llm_ok or vlm_ok:
            self._lbl_server_status.configure(text="🟡 서버 로딩 중...", fg="#f39c12")
        else:
            self._lbl_server_status.configure(text="🔴 도커 서버 오프라인", fg="#e74c3c")
            
        self.after(3000, self._poll_server_status)

    # ==================================================================
    #  Shutdown
    # ==================================================================
    def _on_close(self):
        """Graceful shutdown."""
        logger.info("Shutting down…")
        self._worker.request_shutdown()
        self.destroy()
