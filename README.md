# LadyLisa

LadyLisa is a desktop application built using **Electron** and **Python** that integrates **OCR** (Optical Character Recognition), **Text-to-Speech** (TTS), and **code debugging assistance** into a unified interface. The application uses `orchestrator.py` to coordinate communication between the Electron-based frontend and the Python backend.

---

## 1. Problem Statement

Developers and general users often rely on multiple standalone tools for tasks such as text extraction from images, speech synthesis, and code debugging. This fragmented workflow leads to inefficiency, increased context switching, and complex setup processes.

There is a need for a single, integrated solution that simplifies these tasks within a unified environment.

## 2. Proposed Solution

LadyLisa addresses these challenges by providing a consolidated desktop application that combines:

- **Optical Character Recognition** using Tesseract
- **Text-to-Speech** functionality using Piper
- **Code debugging** assistance tools
- A lightweight and responsive **Electron-based** user interface

This integration reduces dependency on multiple tools and improves productivity by streamlining workflows.

## 3. System Overview

The application follows a hybrid architecture:

| Layer             | Technology                |
| ------------------| ------------------------- |
| **Frontend**      | Electron (Node.js)        |
| **Backend**       | Python (`orchestrator.py`)|
| **Communication** | Electron IPC              |

### Core Modules

- **OCR Module** — `modules/tessa.py`
- **TTS Module** — `modules/tts.py`
- **Debugging Logic** — integrated within the orchestrator pipeline

---

## 4. Installation

### 4.1 Install Node.js Dependencies

From the project root directory:

```bash
npm install
```

### 4.2 Install Python Dependencies

Using system Python:

```bash
python -m pip install -r requirements.txt
```

Using the existing virtual environment:

```bash
c:/Users/iqand/Downloads/ladylisa/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

---

## 5. External Requirements

The application depends on the following external components:

### 5.1 Tesseract OCR

- Required for OCR functionality via `pytesseract`
- Installation: [https://github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract)

### 5.2 Audio Support (PortAudio)

- Required by `sounddevice` for audio playback
- Install appropriate binaries or compatible Python wheels

### 5.3 Piper Voice Models

- Stored in the `piper/` directory (not managed via pip)
- Required for Text-to-Speech functionality
- Ensure the directory and model files remain intact

---

## 6. Running the Application

From the project root directory:

```bash
npm start
```

This command will:

1. Launch the Electron frontend
2. Automatically start the Python backend (`orchestrator.py`)

---

## 7. Application Workflow

1. The Electron application initializes and spawns the Python backend using:
   ```js
   spawn("python", ["orchestrator.py"]);
   ```
2. Communication between frontend and backend is handled using Electron IPC mechanisms
3. Backend processes OCR, TTS, and debugging tasks and returns results to the UI

---

## 8. Notes

- Ensure all dependencies are installed before execution
- Missing Python packages (e.g., `PyQt6`, `requests`) can be installed using:
  ```bash
  pip install -r requirements.txt
  ```
- Verify that external tools such as Tesseract and audio drivers are properly configured

---

## 9. Future Enhancements

- Improved UI/UX with advanced animations
- Enhanced debugging capabilities
- Additional voice models and multilingual support
- Cloud-based processing integration
