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
TTS_STATUS_FILE = TEMP_DIR / "tts_status.txt"
TEMP_DIR.mkdir(exist_ok=True)

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
            if f.is_file():
                f.unlink()
        except:
            pass


def wait_for_tts_ack(start_time, timeout=30):
    while time.time() - start_time < timeout:
        if TTS_STATUS_FILE.exists():
            try:
                status = TTS_STATUS_FILE.read_text(encoding="utf-8").strip()
                if TTS_STATUS_FILE.stat().st_mtime > start_time:
                    # Only return on COMPLETION statuses, not "received"
                    if status.startswith("played") or status in ("playback-error", "failed", "loop-error"):
                        return status
            except:
                pass
        time.sleep(0.2)
    return None


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
        # Kill any stale TTS daemon from previous runs
        pid_file = TEMP_DIR / "tts.pid"
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                import signal
                os.kill(old_pid, signal.SIGTERM)
                log(f"Killed stale TTS daemon PID {old_pid}")
            except (ProcessLookupError, ValueError, OSError):
                pass
        self.process = run_subprocess(MODULES_DIR / "tts.py", PYTHON_EXEC)

    def speak(self, text):
        try:
            if TTS_STATUS_FILE.exists():
                TTS_STATUS_FILE.unlink()
        except:
            pass

        with open(TEMP_DIR / "tts_input.txt", "w", encoding="utf-8") as f:
            f.write(text)

    def wait_for_ack(self, timeout=10):
        return wait_for_tts_ack(time.time(), timeout=timeout)

    def shutdown(self):
        if self.process:
            self.process.terminate()

# -----------------------------
# ORCHESTRATOR
# -----------------------------

class Orchestrator:
    def __init__(self):
        self.tts = XTTS()

    async def announce(self, text, wait_for_tts=True):
        send("text", text)
        self.tts.speak(text)

        if wait_for_tts:
            ack = self.tts.wait_for_ack(timeout=10)
            log(f"TTS announced text, ack={ack}")

    async def acknowledge_choice(self):
        self.tts.speak("Copy that.")
        ack = self.tts.wait_for_ack(timeout=10)
        log(f"TTS acknowledged choice, ack={ack}")
        time.sleep(1)

    async def prompt_with_buttons(self, text, buttons):
        await self.announce(text)
        send("buttons", buttons)

        event = receive()
        if not event or "data" not in event:
            return None

        await self.acknowledge_choice()
        return event

    async def buttons_only(self, buttons):
        send("buttons", buttons)

        event = receive()
        if not event or "data" not in event:
            return None

        await self.acknowledge_choice()
        return event

    async def prompt_with_files(self, text, files):
        await self.announce(text)
        send("files", files)

        event = receive()
        if not event or "data" not in event:
            return None

        await self.acknowledge_choice()
        return event

    async def run(self):
        clear_temp()
        self.tts.start()

        listener = HotkeyListener()
        listener.start()

        while True:
            try:
                listener.wait_for_trigger()

                capture_start = time.time()

                try:
                    wait_for_latest("capture", "png", capture_start)
                except TimeoutError:
                    log("Capture cancelled")
                    await self.announce("Capture cancelled. Press shortcut again.")
                    continue

                # OCR (FIXED EXEC)
                await self.announce("Processing capture and running OCR.")
                ocr_start = time.time()
                run_subprocess(MODULES_DIR / "tessa.py", PYTHON_EXEC)

                try:
                    ocr_file = wait_for_latest("ocr", "txt", ocr_start)
                except TimeoutError:
                    await self.announce("OCR did not return any text. Try another screenshot.")
                    continue

                # Folder selection
                event = await self.prompt_with_buttons("Select your project folder", ["Select Folder"])
                if not event or not event.get("data"):
                    await self.announce("No folder selected. Try again.")
                    continue

                project_path = event.get("data")

                try:
                    engine = ContextEngine()
                    engine.set_project(project_path)
                except Exception as e:
                    await self.announce(f"Invalid project folder: {e}")
                    continue

                files = engine.list_files()

                if not files:
                    await self.announce("No supported code files found. Select a folder with .py, .c, or .cpp files.")
                    continue

                if len(files) > 1:
                    event = await self.prompt_with_files("Which file caused the error?", files)
                    if not event:
                        await self.announce("File selection failed.")
                        continue

                    selected_file = event.get("data")
                    if selected_file not in files:
                        await self.announce("Selected file is not in the project list.")
                        continue
                else:
                    selected_file = files[0]

                # Explanation
                await self.announce("Generating explanation.")
                mini = MiniExplanationEngine()

                with open(ocr_file, "r", encoding="utf-8") as f:
                    ocr_text = f.read()

                temp_json = TEMP_DIR / "mini_input.json"

                with open(temp_json, "w", encoding="utf-8") as f:
                    json.dump({"error": ocr_text}, f)

                explanation_file = mini.explain_from_json(str(temp_json))

                with open(explanation_file, "r", encoding="utf-8") as f:
                    text = f.read()

                await self.announce(text)

                # Fix
                event = await self.buttons_only(["Fix", "Skip"])

                if event and event.get("data") == "Fix":
                    await self.handle_fix(selected_file, engine, ocr_text)
                elif not event:
                    await self.announce("No selection received. Returning to standby.")
                    continue

                # Retry loop
                while True:
                    event = await self.prompt_with_buttons("Are you satisfied?", ["Retry", "Satisfied"])
                    if not event:
                        await self.announce("No selection received. Returning to standby.")
                        break

                    if event.get("data") == "Retry":
                        await self.handle_fix(selected_file, engine, ocr_text, retry=True)

                    elif event.get("data") == "Satisfied":
                        await self.announce("Waiting for next trigger...")
                        break

            except Exception as e:
                log(f"Pipeline error: {e}")
                await self.announce(f"Pipeline error: {e}")

    async def handle_fix(self, selected_file, engine, error_text, retry=False):
        label = "Retrying fix." if retry else "Generating fix."
        await self.announce(label)

        pb = PromptBuilder()
        code = engine.file_ops.get_file_content(selected_file)
        language = engine.context.detect_language(selected_file)

        result = pb.run({
            "type": "code",
            "file": selected_file,
            "language": language,
            "error_clean": error_text,
            "context": {"full_file": code}
        }, retry=retry)

        if result.get("status") != "success" or not result.get("file"):
            fail_label = "Retry" if retry else "Fix generation"
            await self.announce(f"{fail_label} failed: {result.get('message', 'Unknown error')}")
            return

        applied = engine.apply_fix(result["file"], selected_file)
        await self.announce(f"New file created: {applied['file']}")

# -----------------------------
# ENTRY
# -----------------------------

if __name__ == "__main__":
    multiprocessing.freeze_support()
    orch = Orchestrator()
    asyncio.run(orch.run())
