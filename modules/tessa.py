import cv2
import pytesseract
import os
import time
import numpy as np
import re

# -----------------------------
# CONFIG
# -----------------------------

# 🔥 FORCE TESSERACT PATH (IMPORTANT)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TEMP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "temp"
)

# 🔥 ENSURE TEMP DIRECTORY EXISTS
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


# -----------------------------
# 1. GET LATEST IMAGE
# -----------------------------

def get_latest_image(temp_dir):
    files = [
        os.path.join(temp_dir, f)
        for f in os.listdir(temp_dir)
        if f.endswith(".png")
    ]

    if not files:
        return None

    return max(files, key=os.path.getctime)


# -----------------------------
# 2. TERMINAL DETECTION
# -----------------------------

def is_terminal_screen(gray, text):
    mean = gray.mean()
    std = gray.std()

    visual_ok = (mean < 200) and (std > 20)

    lines = [l for l in text.split("\n") if l.strip()]
    density_ok = len(lines) >= 5

    terminal_chars = ["$", ">", ":", "/", "\\"]
    char_score = sum(any(c in line for c in terminal_chars) for line in lines)
    char_ok = char_score >= 2

    return sum([visual_ok, density_ok, char_ok]) >= 2


# -----------------------------
# 3. PREPROCESSING
# -----------------------------

def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if gray.mean() < 127:
        gray = cv2.bitwise_not(gray)

    h, w = gray.shape

    scale = 3 if w < 1000 else 2

    resized = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC
    )

    return resized


# -----------------------------
# 4. CLEAN OUTPUT
# -----------------------------

def clean_text(raw_text):
    lines = raw_text.split("\n")

    ignore_words = [
        "PROBLEMS", "OUTPUT", "DEBUG CONSOLE",
        "TERMINAL", "PORTS"
    ]

    clean_lines = []
    for line in lines:
        line = line.strip()

        if not line:
            continue

        if any(word in line.upper() for word in ignore_words):
            continue

        clean_lines.append(line)

    return "\n".join(clean_lines)


# -----------------------------
# 5. PATH PROCESSING
# -----------------------------

def merge_broken_paths(text):
    lines = text.split("\n")
    merged_lines = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if re.search(r"[A-Za-z]:[\\/]", line):
            combined = line
            j = i + 1

            while j < len(lines):
                next_line = lines[j].strip()

                if re.search(r"(CTRL|Error|Exception|Traceback|Hotkeys)", next_line):
                    break

                if "/" in next_line or "\\" in next_line:
                    combined += next_line
                    j += 1
                else:
                    break

            merged_lines.append(combined)
            i = j
        else:
            merged_lines.append(line)
            i += 1

    return "\n".join(merged_lines)


def clean_path(path):
    path = path.replace(" ", "")
    path = path.replace("Loc:", "Local")
    path = path.replace("Appbata", "AppData")
    path = path.replace("Prograns", "Programs")
    return path


def fix_paths_in_text(text):
    pattern = r"[A-Za-z]:[\\/][^\n]+"

    def replacer(match):
        return clean_path(match.group(0))

    return re.sub(pattern, replacer, text)


def process_ocr_output(text):
    text = merge_broken_paths(text)
    text = fix_paths_in_text(text)
    return text


def process_saved_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    processed = process_ocr_output(text)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(processed)


# -----------------------------
# 6. SAVE OUTPUT
# -----------------------------

def save_output(text, temp_dir):
    filename = f"ocr_output_{int(time.time())}.txt"
    path = os.path.join(temp_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"[OCR] Output saved: {path}")
    return path


# -----------------------------
# 7. MAIN PIPELINE
# -----------------------------

def extract_text_from_screenshot():
    image_path = get_latest_image(TEMP_DIR)

    if not image_path:
        print("[OCR] No image found")
        return

    print(f"[OCR] Processing image: {image_path}")

    img = cv2.imread(image_path)

    if img is None:
        print("[OCR] Failed to load image")
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Pre-check (light OCR)
    pre_text = pytesseract.image_to_string(gray, config="--psm 6")

    if not is_terminal_screen(gray, pre_text):
        print("[OCR] Not a terminal screen, continuing anyway...")

    # Main OCR
    processed = preprocess(img)

    raw_text = pytesseract.image_to_string(
        processed,
        config="--oem 3 --psm 6"
    )

    clean = clean_text(raw_text)

    if not clean.strip():
        print("[OCR] No meaningful text extracted")
        return

    output_path = save_output(clean, TEMP_DIR)
    process_saved_file(output_path)


def run_ocr():
    """Legacy function for backward compatibility."""
    extract_text_from_screenshot()


# -----------------------------
# ENTRY
# -----------------------------

if __name__ == "__main__":
    print("[OCR] Starting OCR module...")
    run_ocr()