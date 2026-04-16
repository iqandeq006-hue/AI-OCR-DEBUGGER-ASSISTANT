import asyncio
import os
import sys
import time
import subprocess
from pathlib import Path
import ctypes
import ctypes.wintypes
import multiprocessing
import threading
import json

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "modules"))

TEMP_DIR = BASE_DIR / "temp"
MODULES_DIR = BASE_DIR / "modules"

# 🔥 GLOBAL PYTHON (FIXED)
PYTHON_EXEC = sys.executable

from nssc import start_capture, start_region_selection, capture_from_region
from config import get_region, clear_region
from cont import ContextEngine
from mini import MiniExplanationEngine
from prompt import PromptBuilder

# -----------------------------
# IPC
# -----------------------------

def send(event_type, data):
    print(json.dumps({"type": event_type, "data": data}), flush=True)

def receive():
    try:
        line = sys.stdin.readline()
        return json.loads(line.strip())
    except:
        return None

# -----------------------------
# UTIL
# -----------------------------

def log(msg):
    print(f"[Orchestrator] {msg}")

def wait_for_latest(prefix, extension, start_time, timeout=30):
    while time.time() - start_time < timeout:
        files = list(TEMP_DIR.glob(f"{prefix}*.{extension}"))
        if files:
            latest = max(files, key=lambda f: f.stat().st_mtime)
            if latest.stat().st_mtime > start_time:
                return latest
        time.sleep(0.3)
    raise TimeoutError(f"{prefix}*.{extension} not found")

def clear_temp():
    for f in TEMP_DIR.glob("*"):
        try:
            f.unlink()
        except:
            pass

def run_subprocess(script_path, python_path):
    return subprocess.Popen(
        [str(python_path), str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(BASE_DIR)
    )

# -----------------------------
# STATE
# -----------------------------

COOLDOWN_TIME = 2

class StateManager:
    def __init__(self):
        self.is_busy = False
        self.last_trigger_time = 0

    def can_trigger(self):
        now = time.time()
        if self.is_busy or (now - self.last_trigger_time < COOLDOWN_TIME):
            return False
        self.is_busy = True
        self.last_trigger_time = now
        return True

    def release(self):
        self.is_busy = False

state = StateManager()

# -----------------------------
# TRIGGER
# -----------------------------

def safe_wrapper(func, *args):
    try:
        func(*args)
    except Exception as e:
        print("Process crashed:", e)

def trigger(func, *args):
    if not state.can_trigger():
        return None

    p = multiprocessing.Process(target=safe_wrapper, args=(func, *args))
    p.start()

    def monitor():
        p.join()
        state.release()

    threading.Thread(target=monitor, daemon=True).start()
    return p

# -----------------------------
# HOTKEY
# -----------------------------

class HotkeyListener:
    def __init__(self):
        self.user32 = ctypes.windll.user32

        self.MOD_CONTROL = 0x0002
        self.MOD_ALT = 0x0001

        self.VK_E = 0x45
        self.VK_S = 0x53
        self.VK_C = 0x43

        self.HOTKEY_CAPTURE = 1
        self.HOTKEY_SAVED = 2
        self.HOTKEY_CLEAR = 3

    def start(self):
        self.user32.RegisterHotKey(None, self.HOTKEY_CAPTURE, self.MOD_CONTROL | self.MOD_ALT, self.VK_E)
        self.user32.RegisterHotKey(None, self.HOTKEY_SAVED, self.MOD_CONTROL | self.MOD_ALT, self.VK_S)
        self.user32.RegisterHotKey(None, self.HOTKEY_CLEAR, self.MOD_CONTROL | self.MOD_ALT, self.VK_C)

    def wait_for_trigger(self):
        msg = ctypes.wintypes.MSG()

        while self.user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:

                if msg.wParam == self.HOTKEY_CAPTURE:
                    trigger(start_capture)
                    return

                elif msg.wParam == self.HOTKEY_SAVED:
                    region = get_region()
                    if region:
                        trigger(capture_from_region, region)
                    else:
                        trigger(start_region_selection)
                    return

                elif msg.wParam == self.HOTKEY_CLEAR:
                    clear_region()

            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageA(ctypes.byref(msg))

# -----------------------------
# TTS (UNCHANGED LOGIC, FIXED EXEC)
# -----------------------------

class XTTS:
    def __init__(self):
        self.process = None

    def start(self):
        self.process = run_subprocess(MODULES_DIR / "tts.py", PYTHON_EXEC)

    def speak(self, text):
        with open(TEMP_DIR / "tts_input.txt", "w") as f:
            f.write(text)

    def shutdown(self):
        if self.process:
            self.process.terminate()

# -----------------------------
# ORCHESTRATOR
# -----------------------------

class Orchestrator:
    def __init__(self):
        self.tts = XTTS()

    async def run(self):
        clear_temp()
        self.tts.start()

        listener = HotkeyListener()
        listener.start()

        while True:

            listener.wait_for_trigger()

            capture_start = time.time()

            try:
                wait_for_latest("capture", "png", capture_start)
            except TimeoutError:
                log("Capture cancelled")
                send("text", "Capture cancelled. Press shortcut again.")
                continue

            # OCR (FIXED EXEC)
            ocr_start = time.time()
            run_subprocess(MODULES_DIR / "tessa.py", PYTHON_EXEC)
            ocr_file = wait_for_latest("ocr", "txt", ocr_start)

            # Folder selection
            send("text", "Select your project folder")
            send("buttons", ["Select Folder"])

            event = receive()
            if not event or "data" not in event:
                send("text", "No input received. Try again.")
                continue

            project_path = event.get("data")

            engine = ContextEngine()
            engine.set_project(project_path)

            files = engine.list_files()

            if len(files) > 1:
                send("text", "Which file caused the error?")
                send("files", files)

                event = receive()
                if not event or "data" not in event:
                    send("text", "File selection failed.")
                    continue

                selected_file = event.get("data")
            else:
                selected_file = files[0]

            # Explanation
            mini = MiniExplanationEngine()

            with open(ocr_file, "r", encoding="utf-8") as f:
                ocr_text = f.read()

            temp_json = TEMP_DIR / "mini_input.json"

            with open(temp_json, "w") as f:
                json.dump({"error": ocr_text}, f)

            explanation_file = mini.explain_from_json(str(temp_json))
            text = open(explanation_file).read()

            send("text", text)
            self.tts.speak(text)

            # Fix
            send("buttons", ["Fix", "Skip"])
            event = receive()

            if event and event.get("data") == "Fix":
                await self.handle_fix(selected_file, engine)

            # Retry loop
            while True:
                send("text", "Are you satisfied?")
                send("buttons", ["Retry", "Satisfied"])

                event = receive()
                if not event:
                    continue

                if event.get("data") == "Retry":
                    await self.handle_retry(selected_file, engine)

                elif event.get("data") == "Satisfied":
                    send("text", "Waiting for next trigger...")
                    break

    async def handle_fix(self, selected_file, engine):
        pb = PromptBuilder()
        code = engine.file_ops.get_file_content(selected_file)

        result = pb.run({
            "type": "code",
            "file": selected_file,
            "language": "python",
            "error_clean": "",
            "context": {"full_file": code}
        })

        engine.apply_fix(result["file"], selected_file)

    async def handle_retry(self, selected_file, engine):
        pb = PromptBuilder()
        code = engine.file_ops.get_file_content(selected_file)

        result = pb.run({
            "type": "code",
            "file": selected_file,
            "language": "python",
            "error_clean": "",
            "context": {"full_file": code}
        }, retry=True)

        engine.apply_fix(result["file"], selected_file)

        send("text", f"New file created: {Path(result['file']).name}")

# -----------------------------
# ENTRY
# -----------------------------

if __name__ == "__main__":
    multiprocessing.freeze_support()
    orch = Orchestrator()
    asyncio.run(orch.run())