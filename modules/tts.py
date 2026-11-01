import os
import time
import subprocess
import json
import sounddevice as sd
import soundfile as sf

# -----------------------------
# CONFIG
# -----------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(BASE_DIR, "temp", "tts_input.txt")
AUDIO_DIR = os.path.join(BASE_DIR, "temp", "audio")
STOP_FILE = os.path.join(BASE_DIR, "temp", "tts_stop.signal")
STATUS_FILE = os.path.join(BASE_DIR, "temp", "tts_status.txt")
DEVICE_CONFIG_FILE = os.path.join(BASE_DIR, "temp", "tts_device_choice.json")
PID_FILE = os.path.join(BASE_DIR, "temp", "tts.pid")

# 🔥 PIPER PATHS
PIPER_PATH = os.path.join(BASE_DIR, "piper", "piper.exe")
VOICE_MODEL = os.path.join(BASE_DIR, "piper", "voices", "en_US-lessac-medium.onnx")

os.makedirs(AUDIO_DIR, exist_ok=True)

print("[Piper TTS] Initializing...")


# -----------------------------
# 🔥 RESOLVE DEVICE (FIXED)
# -----------------------------
def resolve_output_device():
    if os.path.exists(DEVICE_CONFIG_FILE):
        try:
            with open(DEVICE_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            device_index = data.get("device_index")

            if isinstance(device_index, int):
                devices = sd.query_devices()
                name = devices[device_index]["name"]

                # 🔥 HARD LOCK device globally
                sd.default.device = (None, device_index)

                print(f"[Piper TTS] Using LOCKED output device {device_index}: {name}")
                return device_index

        except Exception as e:
            print("[Piper TTS] Failed to read configured output device:", e)

    # fallback
    try:
        default_out = sd.default.device[1]
        print(f"[Piper TTS] Using system default device: {default_out}")
        return default_out
    except Exception as e:
        print("[Piper TTS] No output device available:", e)
        return None


# -----------------------------
# DEVICE UTILS (UNCHANGED)
# -----------------------------
def list_output_devices():
    devices = []
    try:
        for i, device in enumerate(sd.query_devices()):
            if device.get("max_output_channels", 0) > 0:
                devices.append({
                    "index": i,
                    "name": device.get("name", ""),
                    "channels": device.get("max_output_channels", 0),
                    "default_samplerate": device.get("default_samplerate")
                })
    except Exception as e:
        print("[Piper TTS] Failed to enumerate output devices:", e)

    return devices


def save_output_device_choice(device_index, reason="manual-test"):
    try:
        device = sd.query_devices()[device_index]
        payload = {
            "device_index": device_index,
            "device_name": device.get("name", ""),
            "reason": reason
        }
        with open(DEVICE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print(f"[Piper TTS] Saved device {device_index}: {payload['device_name']}")
        return True

    except Exception as e:
        print("[Piper TTS] Failed to save device:", e)
        return False


# -----------------------------
# 🔥 PLAY AUDIO (FIXED — FULL BUFFER)
# -----------------------------
def _stream_audio(data, samplerate, device):
    """Play full audio buffer on a device with stop-signal support."""
    CHUNK = 4096
    import numpy as np

    data = data.astype(np.float32)

    if data.ndim == 1:
        data = data.reshape(-1, 1)

    with sd.OutputStream(samplerate=samplerate, channels=data.shape[1], device=device) as stream:
        for i in range(0, len(data), CHUNK):
            if os.path.exists(STOP_FILE):
                print("[Piper TTS] Stop signal received")
                try:
                    os.remove(STOP_FILE)
                except:
                    pass
                return False
            stream.write(data[i:i + CHUNK])
    return True


def play_audio(file_path, device=None):
    try:
        data, samplerate = sf.read(file_path)

        if device is not None:
            output_device = device
        else:
            output_device = resolve_output_device()

        print(f"[Piper TTS] Playing on device: {output_device}")

        # PRIMARY PLAYBACK
        try:
            if _stream_audio(data, samplerate, output_device):
                return True
        except Exception as e:
            print("[Piper TTS] Primary device failed:", e)

        # FALLBACK
        try:
            fallback = sd.default.device[1]
            print(f"[Piper TTS] Trying fallback device: {fallback}")
            if _stream_audio(data, samplerate, fallback):
                return True
        except Exception as e:
            print("[Piper TTS] Fallback failed:", e)

        return False

    except Exception as e:
        print("[Piper TTS] Playback error:", e)
        return False


# -----------------------------
# GENERATE AUDIO (UNCHANGED)
# -----------------------------
def generate_audio(text):
    filename = f"{hash(text)}.wav"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath):
        print("[Piper TTS] Using cached audio")
        return filepath

    print("[Piper TTS] Generating audio...")

    try:
        process = subprocess.Popen(
            [
                PIPER_PATH,
                "--model", VOICE_MODEL,
                "--output_file", filepath
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        process.communicate(input=text.encode("utf-8"))

        if not os.path.exists(filepath):
            print("[Piper TTS] Audio file not created")
            return None

        return filepath

    except Exception as e:
        print("[Piper TTS] Generation failed:", e)
        return None


# -----------------------------
# MAIN LOOP (UNCHANGED)
# -----------------------------
def write_status(message):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(message)
    except:
        pass


def main_loop():
    print("[Piper TTS] Ready...")

    while True:
        if os.path.exists(INPUT_FILE):
            try:
                with open(INPUT_FILE, "r", encoding="utf-8") as f:
                    text = f.read().strip()

                if text:
                    write_status("received")

                    audio_file = generate_audio(text)

                    if audio_file:
                        if play_audio(audio_file):
                            write_status(f"played:{os.path.basename(audio_file)}")
                        else:
                            write_status("playback-error")
                    else:
                        write_status("failed")

                os.remove(INPUT_FILE)

            except Exception as e:
                print("[Piper TTS] Loop error:", e)
                write_status("loop-error")

        time.sleep(0.2)


# -----------------------------
# SINGLETON LOCK
# -----------------------------
def kill_old_daemon():
    """Kill any previous TTS daemon and claim the PID lock."""
    import signal

    # Kill old process if PID file exists
    if os.path.exists(PID_FILE):
        try:
            old_pid = int(open(PID_FILE, "r").read().strip())
            os.kill(old_pid, signal.SIGTERM)
            print(f"[Piper TTS] Killed old daemon (PID {old_pid})")
        except (ProcessLookupError, ValueError, OSError):
            pass

    # Write current PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    print(f"[Piper TTS] Locked as PID {os.getpid()}")


# -----------------------------
# ENTRY
# -----------------------------
if __name__ == "__main__":
    kill_old_daemon()
    main_loop()