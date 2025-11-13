from flask import Flask, jsonify, render_template
from flask_cors import CORS
import importlib.util
import os
import subprocess
import sys
from typing import Callable, Dict, List, Optional

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


def _load_attr_from_file(module_name: str, relative_path: str, attr_name: str) -> Optional[Callable]:
    file_path = os.path.join(HERE, relative_path)
    if not os.path.isfile(file_path):
        return None
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return getattr(module, attr_name, None)


build_network_device_list = None
for candidate in (
    "HomeNetSafe.website.scan_device",
    "website.scan_device",
):
    try:
        module = __import__(candidate, fromlist=["build_network_device_list"])
        build_network_device_list = getattr(module, "build_network_device_list", None)
        if build_network_device_list:
            break
    except ImportError:
        continue

if build_network_device_list is None:
    for rel in (
        os.path.join("HomeNetSafe", "website", "scan_device.py"),
        os.path.join("website", "scan_device.py"),
    ):
        build_network_device_list = _load_attr_from_file(f"hns_scan_{hash(rel)}", rel, "build_network_device_list")
        if build_network_device_list:
            break


get_local_ip_address = None
for candidate in (
    "src.get_local_ip_address",
    "HomeNetSafe.src.get_local_ip_address",
):
    try:
        module = __import__(candidate, fromlist=["get_local_ip_address"])
        get_local_ip_address = getattr(module, "get_local_ip_address", None)
        if get_local_ip_address:
            break
    except ImportError:
        continue

if get_local_ip_address is None:
    for rel in (
        os.path.join("src", "get_local_ip_address.py"),
        os.path.join("HomeNetSafe", "src", "get_local_ip_address.py"),
    ):
        get_local_ip_address = _load_attr_from_file(f"hns_ip_{hash(rel)}", rel, "get_local_ip_address")
        if get_local_ip_address:
            break

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


def _serialize_registry(registry: Dict[str, dict]) -> List[dict]:
    """Convert the device registry into JSON-friendly rows."""
    rows: List[dict] = []
    for ip, info in registry.items():
        info = info or {}
        rows.append({
            "ip": ip,
            "mac": info.get("mac") or "",
            "vendor": info.get("vendor") or "",
            "first_seen": info.get("first_seen") or "",
            "last_seen": info.get("last_seen") or "",
            "status": info.get("status") or "",
            "name": info.get("name") or info.get("custom_name") or ""
        })
    rows.sort(key=lambda item: item.get("ip") or "")
    return rows


def _detect_local_ip() -> Optional[str]:
    if get_local_ip_address is None:
        return None
    try:
        return get_local_ip_address()
    except Exception:
        return None


@app.get("/get_network_device_list")
def get_network_device_list():
    if build_network_device_list is None:
        return jsonify({
            "devices": [],
            "local_ip": None,
            "error": "Scanner module unavailable"
        }), 500

    try:
        registry = build_network_device_list()
    except Exception as exc:  # pragma: no cover - surfaced to frontend
        return jsonify({
            "devices": [],
            "local_ip": None,
            "error": str(exc)
        }), 500

    devices = _serialize_registry(registry)
    return jsonify({
        "devices": devices,
        "local_ip": _detect_local_ip()
    })

if __name__ == "__main__":
    # Allow the runtime port to be overridden by the PORT environment variable.
    # Default to 5000 for local development, but Docker will set PORT=80.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
