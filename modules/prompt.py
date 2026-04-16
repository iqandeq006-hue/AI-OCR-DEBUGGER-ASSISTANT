import requests
import json
import re
import os
import logging
import subprocess
from datetime import datetime

logging.basicConfig(
    filename="prompt_builder.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class PromptBuilder:
    def __init__(self, model="deepseek-coder:6.7b", temp_dir="temp"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"
        self.temp_dir = temp_dir

        os.makedirs(temp_dir, exist_ok=True)

    # =========================
    # MAIN ENTRY
    # =========================
    def run(self, context_json, retry=False, last_output=None):
        self._validate_context(context_json)

        try:
            if retry:
                prompt = self._build_retry_prompt(context_json, last_output)
            else:
                prompt = self._build_code_prompt(context_json)

            raw = self._call_llm(prompt)
            clean_code = self._sanitize_output(raw)

            if not self._validate_code(clean_code):
                logging.warning("Invalid code → retrying")
                return self.run(context_json, retry=True, last_output=clean_code)

            file_path = self._save_to_temp(clean_code, context_json.get("language"))

            return {
                "status": "success",
                "file": file_path,
                "code": clean_code
            }

        except Exception as e:
            logging.error(f"Run failed: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    # =========================
    # VALIDATION
    # =========================
    def _validate_context(self, ctx):
        if not isinstance(ctx, dict):
            raise ValueError("Context must be a dictionary")

        if "context" not in ctx:
            raise ValueError("Missing 'context' in input")

    def _validate_code(self, code):
        """
        Ensure output is actual code, not explanation
        """
        if not code or len(code) < 10:
            return False

        # Reject obvious explanation text
        bad_patterns = ["error", "reason", "description", "explanation"]
        if any(p.lower() in code.lower() for p in bad_patterns):
            return False

        return True

    # =========================
    # LLM CALL
    # =========================
    def _call_llm(self, prompt):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 800,
                "temperature": 0.1
            }
        }

        try:
            res = requests.post(self.url, json=payload, timeout=60)
            res.raise_for_status()
            return res.json().get("response", "")
        except Exception as e:
            logging.error(f"LLM call failed: {str(e)}")
            return self._call_ollama_cli(prompt)

    def _call_ollama_cli(self, prompt):
        try:
            process = subprocess.Popen(
                ["ollama", "run", self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout, stderr = process.communicate(
                input=prompt.encode("utf-8"),
                timeout=120
            )

            if process.returncode != 0:
                err = stderr.decode("utf-8", errors="ignore").strip()
                raise RuntimeError(err or f"ollama exited with code {process.returncode}")

            return stdout.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            logging.error(f"Ollama CLI fallback failed: {str(e)}")
            raise

    # =========================
    # SANITIZER
    # =========================
    def _sanitize_output(self, text):
        match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return text.strip()

    # =========================
    # CONTEXT PICKER
    # =========================
    def _get_best_context(self, ctx):
        c = ctx.get("context", {})
        return c.get("snippet") or c.get("function") or c.get("full_file") or ""

    # =========================
    # PROMPTS (FIX MODE 🔥)
    # =========================
    def _build_code_prompt(self, ctx):
        code = self._get_best_context(ctx)

        return f"""
You are a strict code fixing engine.

ERROR:
{ctx.get('error_clean')}

LANGUAGE:
{ctx.get('language')}

CODE:
{code}

TASK:
Fix the code completely.

IMPORTANT:
- Fix ALL errors (even hidden ones)
- Ensure code is fully runnable
- Do not miss any issues

RULES:
- Output ONLY the corrected code
- No explanation
- No comments
- No markdown
- No extra text
"""

    def _build_retry_prompt(self, ctx, last_output):
        code = self._get_best_context(ctx)

        return f"""
Previous output was incorrect.

ERROR:
{ctx.get('error_clean')}

CODE:
{code}

PREVIOUS OUTPUT:
{last_output}

TASK:
Fix the code again correctly.

IMPORTANT:
- Ensure the code is fully correct and runnable
- Fix missed errors

RULES:
- Output ONLY corrected code
- No explanation
- No comments
- No markdown
- No extra text
"""

    # =========================
    # SAVE FILE
    # =========================
    def _save_to_temp(self, code, language):
        ext_map = {
            "python": ".py",
            "c": ".c",
            "cpp": ".cpp"
        }

        ext = ext_map.get(language, ".txt")

        file_name = f"fixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        path = os.path.join(self.temp_dir, file_name)

        with open(path, "w", encoding="utf-8") as f:
            f.write(code)

        logging.info(f"Saved file: {path}")
        return path
