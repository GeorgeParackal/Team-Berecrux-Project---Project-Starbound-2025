from flask import Flask, jsonify, render_template
from flask_cors import CORS
import subprocess, sys, os

HERE = os.path.dirname(__file__)
SITE_CANDIDATES = [
    os.path.join(HERE, "HomeNetSafe", "website"),
    os.path.join(HERE, "website"),
]
for base in SITE_CANDIDATES:
    templates_dir = os.path.join(base, "templates")
    static_dir = os.path.join(base, "static")
    if os.path.isdir(templates_dir) and os.path.isdir(static_dir):
        TEMPLATE_DIR = templates_dir
        STATIC_DIR = static_dir
        break
else:
    TEMPLATE_DIR = '.'
    STATIC_DIR = '.'

app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    template_folder=TEMPLATE_DIR,
    static_url_path="/static"
)
CORS(app)

SCRIPT_CANDIDATES = ["DeviceDiscovery.py", "Device Discovery.py"]
SCRIPT_PATH = next((os.path.join(HERE, f) for f in SCRIPT_CANDIDATES if os.path.isfile(os.path.join(HERE, f))), None)

# --- Serve your main HTML website ---
def _render_home():
    return render_template("home.html", temp_var="")


@app.get("/")
def serve_home():
    return _render_home()


@app.get('/home')
def serve_main():
    return _render_home()

# --- Serve your static JS and image files (Flask will auto-handle via static_folder) ---

@app.get("/run-script")
def run_script():
    if not SCRIPT_PATH:
        return jsonify({"ok": False, "stdout": "", "stderr": "Device discovery script not found"}), 500
    try:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH],
            capture_output=True,
            text=True
        )
        # Try to parse common plain-text output from the discovery script
        devices = []
        try:
            import re
            # look for lines like: 192.168.1.10 - AA:BB:CC:11:22:33
            for line in result.stdout.splitlines():
                m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})\s*-\s*([0-9A-Fa-f:]{17})", line)
                if m:
                    devices.append({"ip": m.group(1), "mac": m.group(2)})
        except Exception:
            devices = []

        resp = {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if devices:
            resp["devices"] = devices

        return jsonify(resp), (200 if result.returncode == 0 else 500)
    except Exception as e:
        return jsonify({"ok": False, "stdout": "", "stderr": str(e)}), 500

if __name__ == "__main__":
    # Allow the runtime port to be overridden by the PORT environment variable.
    # Default to 5000 for local development, but Docker will set PORT=80.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
