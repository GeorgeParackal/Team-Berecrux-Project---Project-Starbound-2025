from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import subprocess, sys
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Allow browser requests from your HTML page

BASE_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = BASE_DIR.parent / "src" / "scan_device.py"
UI_FILENAME = "HomeNetSafe2.0.html"

@app.get("/run-script")
def run_script():
    if not SCRIPT_PATH.exists():
        return jsonify({
            "ok": False,
            "stdout": "",
            "stderr": f"Discovery script not found at {SCRIPT_PATH}"
        }), 500
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True
        )
        return jsonify({
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        })
    except Exception as e:
        return jsonify({"ok": False, "stdout": "", "stderr": str(e)}), 500

@app.get("/")
def serve_ui():
    return send_from_directory(BASE_DIR, UI_FILENAME)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
