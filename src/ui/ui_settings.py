"""
AMEVA Voice Screen Assistant — Settings Dialog
================================================
Tkinter Toplevel modal that reads/writes settings directly to ``config.json``
through the ``CFG`` singleton.  Changes take effect immediately.
"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

logger = logging.getLogger("ameva.ui_settings")

# Colors (matching main UI theme)
_CLR_BG       = "#1e1e2e"
_CLR_FG       = "#cdd6f4"
_CLR_ENTRY_BG = "#313244"
_CLR_ACCENT   = "#cba6f7"
_CLR_BTN      = "#45475a"
_CLR_BTN_HOVER= "#585b70"


class SettingsDialog(tk.Toplevel):
    """
    Modal settings dialog.

    Parameters
    ----------
    parent : tk.Tk
    cfg : AppConfig
    db : DatabaseManager  (used only for Docker health check logs)
    """

    def __init__(self, parent, cfg, db):
        super().__init__(parent)
        self.cfg = cfg
        self.db = db

        self.title("⚙ Settings")
        self.geometry("560x520")
        self.resizable(False, False)
        self.configure(bg=_CLR_BG)
        self.transient(parent)
        self.grab_set()

        self._vars: dict[str, tk.StringVar | tk.BooleanVar] = {}
        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Style tweaks for dark theme
        style = ttk.Style()
        style.configure("TNotebook", background=_CLR_BG)
        style.configure("TNotebook.Tab", background=_CLR_BTN, foreground=_CLR_FG, padding=[10, 4])
        style.map("TNotebook.Tab", background=[("selected", _CLR_ACCENT)])

        # --- LLM tab ---
        tab_llm = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_llm, text="LLM")
        self._add_entry(tab_llm, "llm.base_url", "Base URL", row=0)
        self._add_entry(tab_llm, "llm.model_alias", "Model Alias", row=1)
        self._add_entry(tab_llm, "llm.temperature", "Temperature", row=2)
        self._add_entry(tab_llm, "llm.max_tokens", "Max Tokens", row=3)
        self._add_entry(tab_llm, "llm.timeout_sec", "Timeout (sec)", row=4)

        # --- Docker tab ---
        tab_docker = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_docker, text="Docker")
        self._add_entry(tab_docker, "docker.image", "Docker Image", row=0)
        self._add_entry(tab_docker, "docker.container_name", "Container Name", row=1)
        self._add_entry(tab_docker, "docker.port", "Port", row=2)
        
        # Dynamic model selection combo
        self._vars["docker.model_dir"] = tk.StringVar()
        self._vars["docker.model_file"] = tk.StringVar()
        self._vars["docker.mmproj_file"] = tk.StringVar()
        self._add_path_entry(tab_docker, "docker.model_dir", "Model Directory", row=3)
        
        tk.Label(
            tab_docker, text="Model File", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=4, column=0, sticky="w", padx=12, pady=6)
        
        self.model_combo = ttk.Combobox(
            tab_docker, textvariable=self._vars["docker.model_file"],
            font=("Segoe UI", 10), state="readonly", width=37
        )
        self.model_combo.grid(row=4, column=1, sticky="ew", padx=12, pady=6)
        
        tk.Label(
            tab_docker, text="Projector (mmproj)", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=5, column=0, sticky="w", padx=12, pady=6)
        
        self.mmproj_combo = ttk.Combobox(
            tab_docker, textvariable=self._vars["docker.mmproj_file"],
            font=("Segoe UI", 10), state="readonly", width=37
        )
        self.mmproj_combo.grid(row=5, column=1, sticky="ew", padx=12, pady=6)
        tab_docker.columnconfigure(1, weight=1)
        
        # Bind trace to update model list when directory changes
        self._vars["docker.model_dir"].trace_add("write", lambda *args: self._update_model_list())

        # --- Capture tab ---
        tab_cap = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_cap, text="캡처")
        self._add_combo(tab_cap, "capture.mode", "캡처 모드", ["full", "monitor"], row=0)
        self._add_entry(tab_cap, "capture.monitor_index", "모니터 인덱스", row=1)
        self._add_path_entry(tab_cap, "capture.root_dir", "저장 경로", row=2)

        # --- STT/TTS tab ---
        tab_voice = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_voice, text="음성")
        
        # Audio Devices
        try:
            from src.input.audio_input import list_audio_devices
            devices = list_audio_devices()
            
            in_opts = ["기본 마이크 (None)"]
            in_map = {"기본 마이크 (None)": None}
            for d in devices["input"]:
                name = f"[{d['index']}] {d['name']}"
                in_opts.append(name)
                in_map[name] = d['index']
                
            out_opts = ["기본 스피커 (None)"]
            out_map = {"기본 스피커 (None)": None}
            for d in devices["output"]:
                name = d['name']
                out_opts.append(name)
                out_map[name] = name
                
        except Exception as e:
            logger.warning(f"Failed to list audio devices for settings: {e}")
            in_opts, out_opts = ["기본 마이크 (None)"], ["기본 스피커 (None)"]
            in_map, out_map = {"기본 마이크 (None)": None}, {"기본 스피커 (None)": None}

        # Mic Device
        self._device_map_in = in_map
        tk.Label(
            tab_voice, text="마이크 선택", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=6)
        
        self._vars["stt.mic_device_index"] = tk.StringVar()
        current_in = self.cfg.get("stt", "mic_device_index")
        current_in_name = "기본 마이크 (None)"
        for name, idx in in_map.items():
            if idx == current_in and idx is not None:
                current_in_name = name
                break
        self._vars["stt.mic_device_index"].set(current_in_name)
        
        ttk.Combobox(
            tab_voice, textvariable=self._vars["stt.mic_device_index"],
            values=in_opts, font=("Segoe UI", 10), state="readonly", width=37
        ).grid(row=0, column=1, sticky="ew", padx=12, pady=6)
        
        # Speaker Device
        self._device_map_out = out_map
        tk.Label(
            tab_voice, text="스피커 (TTS) 선택", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        
        self._vars["tts.speaker_device"] = tk.StringVar()
        current_out = self.cfg.get("tts", "speaker_device")
        current_out_name = "기본 스피커 (None)"
        for name, dev in out_map.items():
            if dev == current_out and dev is not None:
                current_out_name = name
                break
        self._vars["tts.speaker_device"].set(current_out_name)
        
        ttk.Combobox(
            tab_voice, textvariable=self._vars["tts.speaker_device"],
            values=out_opts, font=("Segoe UI", 10), state="readonly", width=37
        ).grid(row=1, column=1, sticky="ew", padx=12, pady=6)

        # STT settings
        self._add_path_entry(tab_voice, "stt.whisper_executable", "Whisper 실행파일", row=2)
        
        self._vars["stt.model_dir"] = tk.StringVar()
        self._vars["stt.whisper_model"] = tk.StringVar()
        
        tk.Label(
            tab_voice, text="STT 모델 (.bin)", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=3, column=0, sticky="w", padx=12, pady=6)
        
        self.stt_model_combo = ttk.Combobox(
            tab_voice, textvariable=self._vars["stt.whisper_model"],
            font=("Segoe UI", 10), state="readonly", width=37
        )
        self.stt_model_combo.grid(row=3, column=1, sticky="ew", padx=12, pady=6)
        
        self._vars["stt.model_dir"].trace_add("write", lambda *args: self._update_stt_model_list())
        
        # Other settings
        self._add_entry(tab_voice, "stt.silence_timeout_on", "ON 침묵 대기(초)", row=4)
        self._add_entry(tab_voice, "stt.silence_timeout_all", "ALL 침묵 대기(초)", row=5)
        self._add_check(tab_voice, "tts.enabled", "TTS 활성화 (ALL 모드는 강제)", row=6)
        
        tab_voice.columnconfigure(1, weight=1)

        # --- Save / Cancel ---
        btn_frame = tk.Frame(self, bg=_CLR_BG)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        tk.Button(
            btn_frame, text="저장", font=("Segoe UI", 10, "bold"),
            bg=_CLR_ACCENT, fg=_CLR_BG, relief=tk.FLAT,
            cursor="hand2", padx=20, command=self._on_save,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            btn_frame, text="취소", font=("Segoe UI", 10),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT,
            cursor="hand2", padx=20, command=self.destroy,
        ).pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------------
    #  Widget helpers
    # ------------------------------------------------------------------
    def _add_entry(self, parent, key, label, row):
        tk.Label(
            parent, text=label, font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)

        var = tk.StringVar()
        self._vars[key] = var
        entry = tk.Entry(
            parent, textvariable=var, font=("Segoe UI", 10),
            bg=_CLR_ENTRY_BG, fg=_CLR_FG, insertbackground=_CLR_FG,
            relief=tk.FLAT, width=40,
        )
        entry.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        parent.columnconfigure(1, weight=1)

    def _add_path_entry(self, parent, key, label, row):
        tk.Label(
            parent, text=label, font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)

        var = tk.StringVar()
        self._vars[key] = var

        frame = tk.Frame(parent, bg=_CLR_BG)
        frame.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        parent.columnconfigure(1, weight=1)

        entry = tk.Entry(
            frame, textvariable=var, font=("Segoe UI", 10),
            bg=_CLR_ENTRY_BG, fg=_CLR_FG, insertbackground=_CLR_FG,
            relief=tk.FLAT,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            frame, text="…", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, width=3,
            command=lambda: self._browse_path(var),
        ).pack(side=tk.RIGHT, padx=(4, 0))

    def _add_combo(self, parent, key, label, options, row):
        tk.Label(
            parent, text=label, font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)

        var = tk.StringVar()
        self._vars[key] = var
        combo = ttk.Combobox(
            parent, textvariable=var, values=options,
            font=("Segoe UI", 10), state="readonly", width=37,
        )
        combo.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        parent.columnconfigure(1, weight=1)

    def _add_check(self, parent, key, label, row):
        var = tk.BooleanVar()
        self._vars[key] = var
        tk.Checkbutton(
            parent, text=label, variable=var,
            font=("Segoe UI", 10), bg=_CLR_BG, fg=_CLR_FG,
            selectcolor=_CLR_ENTRY_BG, activebackground=_CLR_BG,
            activeforeground=_CLR_FG,
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=6)

    # ------------------------------------------------------------------
    #  Load / Save
    # ------------------------------------------------------------------
    def _load_values(self):
        for key, var in self._vars.items():
            parts = key.split(".")
            val = self.cfg.get(*parts, default="")
            if isinstance(var, tk.BooleanVar):
                var.set(bool(val))
            else:
                # Proactively default model_dir if empty
                if key == "docker.model_dir" and not val:
                    from pathlib import Path
                    if Path("C:/ameva/models/llm").exists():
                        val = "C:/ameva/models/llm"
                var.set(str(val) if val is not None else "")
        
        # Force initial update of model dropdown values
        self._update_model_list()

    def _on_save(self):
        old_dir = self.cfg.get("docker", "model_dir", default="")
        old_file = self.cfg.get("docker", "model_file", default="")
        old_mmproj = self.cfg.get("docker", "mmproj_file", default="")

        for key, var in self._vars.items():
            parts = key.split(".")
            val = var.get()

            # Type coercion for known numeric fields
            if key in ("llm.temperature",):
                try:
                    val = float(val)
                except ValueError:
                    pass
            elif key in ("llm.max_tokens", "llm.timeout_sec", "docker.port",
                         "capture.monitor_index", "stt.recording_max_sec",
                         "stt.silence_timeout_on", "stt.silence_timeout_all"):
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif isinstance(var, tk.BooleanVar):
                val = var.get()

            # Handle mic device selection string mapping back to index
            if key == "stt.mic_device_index":
                val = getattr(self, "_device_map_in", {}).get(val, None)
            # Handle speaker device selection string mapping
            elif key == "tts.speaker_device":
                val = getattr(self, "_device_map_out", {}).get(val, None)

            self.cfg.set(*parts, val)

        new_dir = self._vars["docker.model_dir"].get()
        new_file = self._vars["docker.model_file"].get()
        new_mmproj = self._vars["docker.mmproj_file"].get()
        if new_mmproj == "None":
            new_mmproj = ""

        # Keep llm.model_alias in sync with chosen GGUF file
        if new_file:
            alias = new_file
            if alias.endswith(".gguf"):
                alias = alias[:-5]
            self.cfg.set("llm", "model_alias", alias)

        # If model or mmproj changes, regenerate docker-compose.yml and restart docker
        if new_dir != old_dir or new_file != old_file or new_mmproj != old_mmproj:
            self._update_docker_compose(new_dir, new_file, new_mmproj)
            self._restart_docker_async()

        logger.info("Settings saved")
        messagebox.showinfo("설정", "설정이 저장되었습니다.", parent=self)
        self.destroy()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    def _update_model_list(self):
        from pathlib import Path
        model_dir = self._vars["docker.model_dir"].get()
        if not model_dir:
            self.model_combo["values"] = []
            self.mmproj_combo["values"] = []
            return

        path = Path(model_dir)
        if path.exists() and path.is_dir():
            try:
                all_files = [p.name for p in path.glob("*")]
                
                # Primary models: end with .gguf and do NOT contain mmproj in name
                gguf_models = [f for f in all_files if f.endswith(".gguf") and "mmproj" not in f.lower()]
                sorted_models = sorted(gguf_models)
                self.model_combo["values"] = sorted_models
                
                current_model = self._vars["docker.model_file"].get()
                if sorted_models:
                    if not current_model or current_model not in sorted_models:
                        self._vars["docker.model_file"].set(sorted_models[0])
                else:
                    self._vars["docker.model_file"].set("")
                
                # Projector (mmproj) files: contain mmproj or have .gguf/.bin
                mmproj_files = [f for f in all_files if "mmproj" in f.lower() or f.endswith(".gguf") or f.endswith(".bin")]
                sorted_mmproj = ["None"] + sorted(list(set(mmproj_files)))
                self.mmproj_combo["values"] = sorted_mmproj
                
                current_mmproj = self._vars["docker.mmproj_file"].get()
                if not current_mmproj or current_mmproj not in sorted_mmproj:
                    self._vars["docker.mmproj_file"].set("None")
                    
            except Exception as e:
                logger.error(f"Error scanning model directory: {e}")
                self.model_combo["values"] = []
                self.mmproj_combo["values"] = []
        else:
            self.model_combo["values"] = []
            self.mmproj_combo["values"] = []

    def _update_stt_model_list(self):
        from pathlib import Path
        model_dir = self._vars["stt.model_dir"].get()
        if not model_dir:
            self.stt_model_combo["values"] = []
            return

        path = Path(model_dir)
        if path.exists() and path.is_dir():
            try:
                # STT models for whisper.cpp are usually .bin
                stt_models = [p.name for p in path.glob("*.bin")]
                sorted_models = sorted(stt_models)
                self.stt_model_combo["values"] = sorted_models
                
                current_model = self._vars["stt.whisper_model"].get()
                if sorted_models:
                    if not current_model or current_model not in sorted_models:
                        # Optionally don't auto-set to avoid overriding with wrong model
                        pass
                else:
                    self.stt_model_combo["values"] = []
            except Exception as e:
                logger.error(f"Error scanning STT model directory: {e}")
                self.stt_model_combo["values"] = []
        else:
            self.stt_model_combo["values"] = []

    def _update_docker_compose(self, model_dir: str, model_file: str, mmproj_file: str):
        from pathlib import Path
        compose_path = Path("docker/docker-compose.yml")
        if not compose_path.exists():
            return

        try:
            lines = compose_path.read_text(encoding="utf-8").splitlines()
            new_lines = []
            in_volumes = False
            current_service = None

            for line in lines:
                stripped = line.strip()
                if line.startswith("  ") and line.endswith(":") and not line.startswith("    "):
                    current_service = stripped.rstrip(":")

                if current_service == "llm-server":
                    if stripped == "volumes:":
                        in_volumes = True
                        new_lines.append(line)
                        continue

                    if in_volumes and stripped.startswith("- ") and stripped.endswith(":/models"):
                        indent = line[:line.index("-")]
                        clean_dir = str(Path(model_dir).resolve()).replace("\\", "/")
                        new_lines.append(f"{indent}- {clean_dir}:/models")
                        in_volumes = False
                        continue

                    if stripped.startswith("--model "):
                        indent = line[:line.index("--model")]
                        new_lines.append(f"{indent}--model /models/{model_file}")
                        
                        # Automatically append --mmproj line right after --model if specified
                        if mmproj_file:
                            new_lines.append(f"{indent}--mmproj /models/{mmproj_file}")
                        continue

                    if stripped.startswith("--mmproj "):
                        # Skip the old mmproj line, we regenerate it right after --model
                        continue
                else:
                    if stripped == "volumes:":
                        in_volumes = False

                new_lines.append(line)

            compose_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            logger.info("docker-compose.yml updated with new model and mmproj settings.")
        except Exception as e:
            logger.error(f"Failed to update docker-compose.yml: {e}")

    def _restart_docker_async(self):
        import threading
        import subprocess
        from pathlib import Path

        def run_restart():
            docker_dir = Path("docker")
            logger.info("Restarting docker container with new model settings...")
            try:
                subprocess.run(
                    ["docker", "compose", "down"],
                    cwd=str(docker_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15
                )
                subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    cwd=str(docker_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15
                )
                logger.info("Docker container restarted successfully with new model settings.")
            except Exception as e:
                logger.error(f"Failed to restart Docker compose: {e}")

        threading.Thread(target=run_restart, daemon=True).start()

    @staticmethod
    def _browse_path(var: tk.StringVar):
        path = filedialog.askdirectory()
        if path:
            var.set(path)
