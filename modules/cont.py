import os
import logging

ALLOWED_EXTENSIONS = (".py", ".c", ".cpp")
IGNORE_FOLDERS = {".git", "__pycache__", "node_modules"}
MAX_CONTEXT_SIZE = 5000  # Prevent huge LLM inputs

logging.basicConfig(
    filename="context_engine.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =========================================================
# FILE OPERATIONS (SAFE I/O)
# =========================================================
class FileOperations:
    def __init__(self):
        self.project_path = None

    def set_project_path(self, path):
        if not os.path.isdir(path):
            raise ValueError(f"Invalid project path: {path}")
        self.project_path = path
        logging.info(f"Project path set: {path}")

    def _ensure_project(self):
        if not self.project_path:
            raise ValueError("Project path not set")

    def list_files(self):
        self._ensure_project()
        files = []

        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]

            for file in filenames:
                if file.endswith(ALLOWED_EXTENSIONS):
                    rel_path = os.path.relpath(
                        os.path.join(root, file),
                        self.project_path
                    )
                    files.append(rel_path)

        return sorted(files)

    def get_full_path(self, file_name):
        self._ensure_project()
        return os.path.join(self.project_path, file_name)

    def get_file_content(self, file_name):
        full_path = self.get_full_path(file_name)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_name}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except:
            with open(full_path, "r", encoding="latin-1") as f:
                return f.read()

    # ==============================
    # SAFE NEW FILE CREATION
    # ==============================
    def _generate_new_filename(self, original_name):
        base, ext = os.path.splitext(original_name)
        counter = 1

        while True:
            new_name = f"{base}_fixed_{counter}{ext}"
            full_path = self.get_full_path(new_name)

            if not os.path.exists(full_path):
                return new_name

            counter += 1

    def write_new_file(self, original_name, content):
        """
        ALWAYS creates a new file.
        NEVER overwrites original.
        """
        self._ensure_project()

        new_file_name = self._generate_new_filename(original_name)
        full_path = self.get_full_path(new_file_name)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        logging.info(f"New file created: {new_file_name}")
        return new_file_name


# =========================================================
# CONTEXT RETRIEVER (LOGIC ONLY)
# =========================================================
class ContextRetriever:

    def extract_context(self, code, line=None):
        lines = code.split("\n")
        snippet = None
        function = None

        # -------------------------
        # SNIPPET (around error)
        # -------------------------
        if line:
            start = max(0, line - 10)
            end = min(len(lines), line + 10)
            snippet = "\n".join(lines[start:end])

        # -------------------------
        # FUNCTION (Python only)
        # -------------------------
        function = self._extract_python_function(lines, line)

        return snippet, function

    def _extract_python_function(self, lines, line):
        try:
            start = None

            if line:
                for i in range(line - 1, -1, -1):
                    if lines[i].strip().startswith("def "):
                        start = i
                        break

            if start is None:
                return None

            for j in range(start + 1, len(lines)):
                if lines[j].startswith("def "):
                    return "\n".join(lines[start:j])

            return "\n".join(lines[start:])

        except:
            return None

    def detect_language(self, file_name):
        if file_name.endswith(".py"):
            return "python"
        elif file_name.endswith(".c"):
            return "c"
        elif file_name.endswith(".cpp"):
            return "cpp"
        return "unknown"

    def build_context_json(self, file, code, error_data):
        line = error_data.get("line")

        snippet, function = self.extract_context(code, line)

        # -------------------------
        # LIMIT FULL FILE SIZE
        # -------------------------
        full_file = None
        if not snippet and not function:
            full_file = code[:MAX_CONTEXT_SIZE]

        return {
            "type": "code",
            "file": file,
            "line": line,
            "language": self.detect_language(file),
            "error_clean": error_data.get("error"),
            "context": {
                "snippet": snippet,
                "function": function,
                "full_file": full_file
            }
        }


# =========================================================
# CONTEXT ENGINE (COORDINATOR)
# =========================================================
class ContextEngine:
    def __init__(self):
        self.file_ops = FileOperations()
        self.context = ContextRetriever()

    def set_project(self, path):
        self.file_ops.set_project_path(path)

    def list_files(self):
        return self.file_ops.list_files()

    # ==============================
    # GET CONTEXT FOR PROMPT BUILDER
    # ==============================
    def get_context(self, error_data):
        file = error_data.get("file")

        if not file:
            raise ValueError("Missing 'file' in error_data")

        full_path = self.file_ops.get_full_path(file)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file}")

        code = self.file_ops.get_file_content(file)

        return self.context.build_context_json(file, code, error_data)

    # ==============================
    # APPLY FIX (WRITE TO PROJECT)
    # ==============================
    def apply_fix(self, fixed_file_path, original_file_name):
        """
        Takes validated file from PromptBuilder (temp folder)
        and writes it safely into project folder.
        """

        if not os.path.exists(fixed_file_path):
            raise FileNotFoundError("Fixed file not found from PromptBuilder")

        with open(fixed_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_file = self.file_ops.write_new_file(original_file_name, content)

        return {
            "status": "success",
            "file": new_file
        }