import json
import time
from pathlib import Path

from modules.tts import (
    generate_audio,
    list_output_devices,
    play_audio,
    save_output_device_choice,
)

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
REPORT_FILE = TEMP_DIR / "tts_device_report.json"


# ----------------------------------------
# SMART DEVICE SCORING
# ----------------------------------------
def score_device(result):
    score = 0

    # 1. Must play successfully
    if result["play_ok"]:
        score += 50
    else:
        return 0  # immediately discard

    name = result["name"].lower()

    # 2. Prefer real speakers
    if "speaker" in name:
        score += 20

    # 3. Penalize HDMI / virtual devices
    if "hdmi" in name or "virtual" in name or "vb-audio" in name:
        score -= 10

    # 4. Lower latency = better
    latency = result.get("latency", 999)
    score += max(0, 20 - latency)

    # 5. More channels = slightly better
    score += min(result.get("channels", 0), 8)

    return score


def choose_recommended_device(results):
    scored = []

    for r in results:
        s = score_device(r)
        r["score"] = s
        if s > 0:
            scored.append(r)

    if not scored:
        return None

    # Sort by score (highest first)
    scored.sort(key=lambda x: x["score"], reverse=True)

    return scored[0]


# ----------------------------------------
# MAIN TEST LOGIC
# ----------------------------------------
def main():
    TEMP_DIR.mkdir(exist_ok=True)

    sample_text = "Testing one two three. Clear voice output check."

    print("\n[INFO] Generating sample audio...")
    sample_audio = generate_audio(sample_text)

    if not sample_audio:
        payload = {
            "sample_audio": None,
            "results": [],
            "recommended_device": None,
            "error": "Failed to generate sample audio."
        }
        REPORT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return

    print("[INFO] Audio generated:", sample_audio)

    results = []
    devices = list_output_devices()

    if not devices:
        print("[ERROR] No output devices found!")
        return

    print(f"\n[INFO] Found {len(devices)} output devices\n")

    # ----------------------------------------
    # TEST EACH DEVICE
    # ----------------------------------------
    for device in devices:
        print(f"\n[TESTING] {device['index']} → {device['name']}")

        started = time.time()
        play_ok = False
        error = None

        try:
            play_start = time.time()
            play_ok = play_audio(sample_audio, device=device["index"])
            play_end = time.time()

            latency = round(play_end - play_start, 2)

        except Exception as e:
            error = str(e)
            latency = None

        elapsed = round(time.time() - started, 2)

        result = {
            "index": device["index"],
            "name": device["name"],
            "channels": device["channels"],
            "default_samplerate": device["default_samplerate"],
            "play_ok": bool(play_ok),
            "latency": latency,
            "elapsed_seconds": elapsed,
            "error": error,
        }

        print("   ✔ play_ok:", play_ok)
        print("   ⏱ latency:", latency)
        print("   ⏳ elapsed:", elapsed)

        results.append(result)

    # ----------------------------------------
    # PICK BEST DEVICE
    # ----------------------------------------
    recommended = choose_recommended_device(results)

    if recommended:
        print("\n[RESULT] Best device selected:")
        print(f"   → {recommended['name']} (index {recommended['index']})")
        print(f"   → score: {recommended['score']}")

        save_output_device_choice(recommended["index"], reason="auto-speaker-test")
    else:
        print("\n[WARNING] No suitable device found!")

    # ----------------------------------------
    # SAVE REPORT
    # ----------------------------------------
    payload = {
        "sample_audio": str(sample_audio),
        "results": results,
        "recommended_device": recommended,
    }

    REPORT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n[INFO] Report saved to:", REPORT_FILE)


# ----------------------------------------
# ENTRY
# ----------------------------------------
if __name__ == "__main__":
    main()