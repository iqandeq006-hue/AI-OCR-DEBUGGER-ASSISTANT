import json
import re
import os
import logging
import requests


class MiniExplanationEngine:
    def __init__(self, model="phi:2.7b", temp_dir="temp"):
        self.model = model
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

        log_path = os.path.join(self.temp_dir, "mini_explanation.log")

        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

        self.logger = logging.getLogger(__name__)

    # -------------------------------
    # LOAD JSON
    # -------------------------------
    def load_error_from_json(self, json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            error_text = data.get("error", "").strip()

            if not error_text:
                raise ValueError("Empty error text")

            return error_text

        except Exception:
            self.logger.exception("Failed to load JSON")
            return None

    # -------------------------------
    # CLEAN OCR
    # -------------------------------
    def clean_error_text(self, text):
        if not text:
            return None

        cleaned = re.sub(r'[^\x00-\x7F]+', ' ', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned if cleaned else text

    def condense_error_text(self, text, max_chars=280):
        if not text:
            return None

        priority_patterns = [
            r"syntaxerror:[^\\n]*",
            r"nameerror:[^\\n]*",
            r"typeerror:[^\\n]*",
            r"valueerror:[^\\n]*",
            r"indexerror:[^\\n]*",
            r"keyerror:[^\\n]*",
            r"attributeerror:[^\\n]*",
            r"traceback[^\\n]*",
            r"line\s+\d+[^\\n]*",
            r'file\s+"[^"]+"[^\\n]*',
            r"error:[^\\n]*"
        ]

        pieces = []
        lowered = text.lower()

        for pattern in priority_patterns:
            match = re.search(pattern, lowered, re.IGNORECASE)
            if match:
                snippet = text[match.start():match.end()].strip()
                if snippet and snippet not in pieces:
                    pieces.append(snippet)

        if not pieces:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            pieces = lines[:4]

        condensed = " | ".join(pieces)
        return condensed[:max_chars].strip() or text[:max_chars].strip()

    # -------------------------------
    # PROMPT
    # -------------------------------
    def build_prompt(self, error_text):
        return f"""
Explain this coding error in 2 or 3 short sentences.
Say what is wrong and the likely fix.
Do not add dialogue, labels, or examples unless necessary.

{error_text}
"""

    # -------------------------------
    # MODEL (🔥 FIXED HERE)
    # -------------------------------
    def query_ollama(self, prompt):
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 120,
                        "temperature": 0.1
                    }
                }
            )
            response.raise_for_status()
            output = response.json().get("response", "").strip()
            return output if output else None

        except Exception:
            self.logger.exception("Model failed")
            return None

    # -------------------------------
    # SAVE
    # -------------------------------
    def save_output(self, text):
        path = os.path.join(self.temp_dir, "mini_explanation.txt")

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

        return path

    # -------------------------------
    # MAIN PIPELINE
    # -------------------------------
    def explain_from_json(self, input_json_path):
        try:
            error_text = self.load_error_from_json(input_json_path)

            if not error_text:
                return self.save_output(
                    "Could not read error. Try again."
                )

            cleaned = self.clean_error_text(error_text)

            if not cleaned:
                return self.save_output(
                    "Error text unclear. Try a better screenshot."
                )

            condensed = self.condense_error_text(cleaned)
            prompt = self.build_prompt(condensed or cleaned)

            output = self.query_ollama(prompt)

            if not output:
                return self.save_output(
                    "AI could not understand the error. Try again."
                )

            return self.save_output(output)

        except Exception:
            self.logger.exception("Pipeline crash")

            return self.save_output(
                "Something went wrong. Please retry."
            )
