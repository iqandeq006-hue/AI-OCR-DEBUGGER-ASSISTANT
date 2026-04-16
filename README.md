# LadyLisa

A small Electron + Python application that uses `orchestrator.py` to drive a front-end overlay and a Python backend for OCR, TTS, and code debugging helper logic.

## Installation

### 1. Install Node dependencies

From the project root:

```bash
npm install
```

### 2. Install Python dependencies

Use the project virtual environment if available, or your system Python.

```bash
python -m pip install -r requirements.txt
```

If you want to install into the existing virtual environment directly:

```bash
c:/Users/iqand/Downloads/ladylisa/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## External Requirements

The Python requirements list covers the project packages, but the app also depends on these external components:

- `Tesseract OCR`
  - Required for `pytesseract` in `modules/tessa.py`
  - Install from https://github.com/tesseract-ocr/tesseract

- `PortAudio` or native audio support
  - Required by `sounddevice` for audio playback in `modules/tts.py`
  - On Windows, install the appropriate binary packages or use a Python wheel that bundles PortAudio.

- `piper/` model or voice data files
  - The project includes a `piper/` folder, which is not a pip dependency.
  - Keep the folder contents in place if the app uses them for speech synthesis.

## Run the App

From the project root:

```bash
npm start
```

This launches the Electron frontend and starts `orchestrator.py` automatically.

## Notes

- The Python backend is started by `main.js` using:
  - `spawn("python", ["orchestrator.py"])`
- The front end communicates with Python through Electron IPC.
- If you are missing packages such as `PyQt6` or `requests`, install them via `requirements.txt`.
