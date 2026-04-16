import os
import time
import subprocess
import sounddevice as sd
import soundfile as sf

# -----------------------------
# CONFIG
# -----------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(BASE_DIR, "temp", "tts_input.txt")
AUDIO_DIR = os.path.join(BASE_DIR, "temp", "audio")
STOP_FILE = os.path.join(BASE_DIR, "temp", "tts_stop.signal")

# 🔥 PIPER PATHS (EDIT IF NEEDED)
PIPER_PATH = r"C:\Users\iqand\Downloads\ladylisa\piper\piper.exe"
VOICE_MODEL = r"C:\Users\iqand\Downloads\ladylisa\piper\voices\en_US-lessac-medium.onnx"

# Ensure folders exist
os.makedirs(AUDIO_DIR, exist_ok=True)

print("[Piper TTS] Initializing...")


# -----------------------------
# PLAY AUDIO (STREAMING + STOP)
# -----------------------------

def play_audio(file_path):
    try:
        data, samplerate = sf.read(file_path)

        # Stream playback in chunks (keeps stop control)
        for i in range(0, len(data), 1024):

            # 🔥 Stop signal support
            if os.path.exists(STOP_FILE):
                print("[Piper TTS] Stop signal received")
                os.remove(STOP_FILE)
                return

            sd.play(data[i:i+1024], samplerate)
            sd.wait()

    except Exception as e:
        print("[Piper TTS] Playback error:", e)


# -----------------------------
# GENERATE AUDIO (PIPER)
# -----------------------------

def generate_audio(text):
    filename = f"{hash(text)}.wav"
    filepath = os.path.join(AUDIO_DIR, filename)

    # 🔥 Cache check
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

        # Validate file created
        if not os.path.exists(filepath):
            print("[Piper TTS] Audio file not created")
            return None

        return filepath

    except Exception as e:
        print("[Piper TTS] Generation failed:", e)
        return None


# -----------------------------
# MAIN LOOP
# -----------------------------

def main_loop():
    print("[Piper TTS] Ready...")
    last_text = ""

    while True:
        if os.path.exists(INPUT_FILE):
            try:
                with open(INPUT_FILE, "r", encoding="utf-8") as f:
                    text = f.read().strip()

                if text and text != last_text:
                    last_text = text

                    audio_file = generate_audio(text)

                    if audio_file:
                        play_audio(audio_file)

                # Remove input trigger file
                os.remove(INPUT_FILE)

            except Exception as e:
                print("[Piper TTS] Loop error:", e)

        time.sleep(0.2)


# -----------------------------
# ENTRY
# -----------------------------

if __name__ == "__main__":
    main_loop()