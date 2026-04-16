import json
import subprocess
import re
import os
import logging


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

    # -------------------------------
    # PROMPT
    # -------------------------------
    def build_prompt(self, error_text):
        return f"""
Explain this error simply:

{error_text}
"""

    # -------------------------------
    # MODEL (🔥 FIXED HERE)
    # -------------------------------
    def query_ollama(self, prompt):
        try:
            process = subprocess.Popen(
                ["ollama", "run", self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            stdout, _ = process.communicate(
                input=prompt.encode("utf-8")
            )

            output = stdout.decode("utf-8", errors="ignore").strip()

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

            prompt = self.build_prompt(cleaned)

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