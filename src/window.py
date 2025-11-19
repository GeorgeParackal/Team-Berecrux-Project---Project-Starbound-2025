import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import importlib
import inspect
import time
import csv
import os
import manuf

# =========================
# CONFIG
# =========================
APP_TITLE = "Network Device Scanner"
BG_DARK = "#111827"  # slate-900
CARD = "#1f2937"     # slate-800
ACCENT = "#1f2937"   # blue-600
ACCENT_HOVER = "#9ca3af"  # blue-700
TEXT = "#e5e7eb"     # gray-200
TEXT_MUTED = "#9ca3af"  # gray-400
SUCCESS = "#22c55e"  # green-500
DANGER = "#1f2937"   # red-500
WARNING = "#f59e0b"  # amber-500
ROW_ALT = "#111827"

DEVICE_TTL = 60  # seconds of inactivity before a device is marked inactive
QUEUE_POLL_MS = 100
STATUS_REFRESH_MS = 1000

# =========================
# Best-effort import and live-reload of user scanner
# If unavailable, fall back to a local mock generator so the UI still shines.
# =========================
run_scan = None

try:
    import network_scan  # expected to expose run_scan(callback(mac,vendor,ip), stop_event)
    importlib.reload(network_scan)
    if hasattr(network_scan, "run_scan") and inspect.isfunction(network_scan.run_scan):
        run_scan = network_scan.run_scan
except Exception as e:
    # We'll gracefully fall back to a mock below
    run_scan = None


def _mock_run_scan(on_new_device, stop_event):
    """A friendly mock scanner that emits pretend devices for demo/hire-me runs."""
    vendors = [
        ("D4:6A:6C:AA:01:22", "Ubiquiti Networks", "192.168.1.1"),      # Router
        ("B8:27:EB:12:34:56", "Raspberry Pi Foundation", "192.168.1.42"),
        ("F0:99:B6:77:88:99", "Apple, Inc.", "192.168.1.12"),
        ("60:AB:67:00:00:01", "Samsung Electronics", "192.168.1.33"),
        ("3C:5A:B4:DE:AD:BE", "Intel Corporate", "192.168.1.24"),
    ]
    i = 0
    while not stop_event.is_set():
        mac, vendor, base_ip = vendors[i % len(vendors)]
        # randomly jitter IP last octet for mock 'movement'
        ip = base_ip.rsplit('.', 1)[0] + f".{10 + (i % 50)}"
        on_new_device(mac, vendor, ip)
        i += 1
        time.sleep(0.6)


if run_scan is None:
    run_scan = _mock_run_scan

# =========================
# App State
# =========================
q = queue.Queue()
scan_thread = None
stop_event = threading.Event()
scan_start_time = None

# MAC -> Tk item id
known_devices = {}
# MAC -> last_seen epoch
last_seen = {}

# =========================
# UI Helpers
# =========================

def apply_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Global colors
    root.configure(bg=BG_DARK)

    style.configure("TFrame", background=BG_DARK)
    style.configure("Card.TFrame", background=CARD)

    style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground=TEXT, background=BG_DARK)
    style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground=TEXT_MUTED, background=BG_DARK)
    style.configure("Info.TLabel", font=("Segoe UI", 10), foreground=TEXT, background=CARD)

    style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
    style.map(
        "TButton",
        background=[("active", ACCENT_HOVER)],
        foreground=[("disabled", TEXT_MUTED)],
    )

    style.configure("Accent.TButton", background=ACCENT, foreground="white", borderwidth=0)
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])

    style.configure("Danger.TButton", background=DANGER, foreground="white", borderwidth=0)
    style.map("Danger.TButton", background=[("active", "#dc2626")])

    # Treeview
    style.configure(
        "Treeview",
        background=CARD,
        foreground=TEXT,
        fieldbackground=CARD,
        rowheight=28,
        font=("Segoe UI", 10),
        borderwidth=0,
    )
    style.map("Treeview", background=[("selected", ACCENT)])
    style.configure(
        "Treeview.Heading",
        background=ACCENT,
        foreground="white",
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
    )


# =========================
# Core logic
# =========================

def on_new_device(mac, vendor, ip):
    if not mac:
        return
    vendor = vendor or "Unknown"
    ip = ip or "—"
    q.put((mac, vendor, ip, time.time()))


def device_type_from_vendor(vendor: str) -> str:
    v = vendor.lower()
    if "router" in v or "gateway" in v or "ubiquiti" in v or "netgear" in v or "tp-link" in v or "mikrotik" in v:
        return "🌐 Router"
    if "apple" in v:
        return "🍎 Apple"
    if "samsung" in v:
        return "📱 Samsung"
    if "raspberry" in v:
        return "🧪 Raspberry Pi"
    if "intel" in v or "microsoft" in v or "dell" in v or "hp " in v:
        return "💻 Device"
    return "🔧 Device"


# Sorting helpers
sort_state = {}

def sort_by_column(tree, col):
    data = [(tree.set(k, col), k) for k in tree.get_children("")]

    # Detect type
    def as_key(val):
        # IP-aware sort
        if col == "IP Address" and val and val != "—":
            parts = val.split(".")
            if len(parts) == 4 and all(p.isdigit() for p in parts):
                return tuple(int(p) for p in parts)
        # status priority
        if col == "Status":
            order = {"Active": 0, "Inactive": 1}
            return order.get(val, 2)
        return val.lower() if isinstance(val, str) else val

    reverse = sort_state.get(col, False)
    data.sort(key=lambda x: as_key(x[0]), reverse=reverse)
    for index, (_, k) in enumerate(data):
        tree.move(k, "", index)
    sort_state[col] = not reverse


# =========================
# Tk App
# =========================
root = tk.Tk()
root.title(APP_TITLE)
root.geometry("980x660")
root.minsize(780, 520)

apply_styles(root)

# --- Header ---
header = ttk.Frame(root, style="TFrame")
header.pack(fill="x", padx=16, pady=(16, 8))

lbl_title = ttk.Label(header, text=APP_TITLE, style="Title.TLabel")
lbl_title.pack(anchor="w")

lbl_sub = ttk.Label(
    header,
    text="Version 1.0 Offline Scanner - Designed for proof of concept",
    style="Sub.TLabel",
)
lbl_sub.pack(anchor="w", pady=(6, 0))

# --- Controls Card ---
controls_card = ttk.Frame(root, style="Card.TFrame", padding=14)
controls_card.pack(fill="x", padx=16, pady=8)

btn_frame = ttk.Frame(controls_card, style="Card.TFrame")
btn_frame.pack(side="left")

start_btn = ttk.Button(btn_frame, text="Start Scan", style="Accent.TButton")
stop_btn = ttk.Button(btn_frame, text="Stop Scan", style="Accent.TButton", state="disabled")
export_btn = ttk.Button(btn_frame, text="Export CSV", style="Accent.TButton")

start_btn.grid(row=0, column=0, padx=(0, 8))
stop_btn.grid(row=0, column=1, padx=8)
export_btn.grid(row=0, column=2, padx=8)


# --- Tree Card ---
list_card = ttk.Frame(root, style="Card.TFrame", padding=12)
list_card.pack(fill="both", expand=True, padx=16, pady=(8, 16))

columns = ("Type", "MAC Address", "Vendor", "IP Address", "Status")
tree = ttk.Treeview(list_card, columns=columns, show="headings")

# Configure columns
col_specs = {
    "Type": dict(width=140, anchor="center"),
    "MAC Address": dict(width=170, anchor="center"),
    "Vendor": dict(width=260, anchor="center"),
    "IP Address": dict(width=150, anchor="center"),
    "Status": dict(width=100, anchor="center"),
}

for col in columns:
    tree.heading(col, text=col, anchor="center", command=lambda c=col: sort_by_column(tree, c))
    tree.column(col, **col_specs[col])

# Scrollbar
scrollbar = ttk.Scrollbar(list_card, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)

# Layout
tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Row tags for styling
tree.tag_configure("inactive", foreground=TEXT_MUTED)
tree.tag_configure("alt", background=ROW_ALT)

# --- Status Bar ---
status = ttk.Frame(root, style="TFrame")
status.pack(fill="x", padx=16, pady=(0, 12))

status_var = tk.StringVar(value="Ready to scan network")
count_var = tk.StringVar(value="Devices: 0")

status_lbl = ttk.Label(status, textvariable=status_var, style="Sub.TLabel")
count_lbl = ttk.Label(status, textvariable=count_var, style="Sub.TLabel")
status_lbl.pack(side="left")
count_lbl.pack(side="right")

# Context menu
menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Copy MAC", command=lambda: copy_col(1))
menu.add_command(label="Copy IP", command=lambda: copy_col(3))
menu.add_separator()
menu.add_command(label="Ping (opens terminal)", command=lambda: ping_selected())


def popup_menu(event):
    iid = tree.identify_row(event.y)
    if iid:
        tree.selection_set(iid)
        menu.tk_popup(event.x_root, event.y_root)


# =========================
# Behaviors
# =========================

def copy_col(idx):
    sel = tree.selection()
    if not sel:
        return
    values = tree.item(sel[0], "values")
    try:
        root.clipboard_clear()
        root.clipboard_append(values[idx])
        status_var.set(f"Copied: {values[idx]}")
    except Exception:
        pass


def ping_selected():
    sel = tree.selection()
    if not sel:
        return
    ip = tree.item(sel[0], "values")[3]
    if not ip or ip == "—":
        messagebox.showinfo("Ping", "No IP available to ping.")
        return
    # Open a terminal window with a ping command (best-effort, OS specific)
    try:
        if os.name == "nt":
            os.system(f"start cmd /k ping {ip}")
        elif sys.platform == "darwin":
            os.system(f"open -a Terminal.app 'ping {ip}'")
        else:
            os.system(f"x-terminal-emulator -e ping {ip} || gnome-terminal -- ping {ip} || konsole -e ping {ip}")
    except Exception:
        messagebox.showinfo("Ping", "Couldn't launch a terminal. You can copy the IP and run ping manually.")



def insert_or_update_device(mac, vendor, ip, now_ts):
    device_type = device_type_from_vendor(vendor)
    status_text = "Active"

    if mac in known_devices:
        iid = known_devices[mac]
        cur = tree.item(iid, "values")
        new_vals = (device_type, mac, vendor, ip, status_text)
        if cur != new_vals:
            tree.item(iid, values=new_vals, tags=("",))
    else:
        iid = tree.insert("", "end", values=(device_type, mac, vendor, ip, status_text))
        known_devices[mac] = iid

    last_seen[mac] = now_ts

    # Alternating row backgrounds for readability
    for i, child in enumerate(tree.get_children("")):
        tags = list(tree.item(child, "tags"))
        if i % 2 == 1:
            if "alt" not in tags:
                tags.append("alt")
        else:
            if "alt" in tags:
                tags.remove("alt")
        tree.item(child, tags=tuple(tags))



def poll_queue():
    # Pull everything quickly so UI stays snappy
    try:
        while True:
            mac, vendor, ip, ts = q.get_nowait()
            insert_or_update_device(mac, vendor, ip, ts)
    except queue.Empty:
        pass
    root.after(QUEUE_POLL_MS, poll_queue)



def refresh_statuses():
    now = time.time()
    # mark inactive if stale
    for mac, iid in list(known_devices.items()):
        seen = last_seen.get(mac, 0)
        idle = now - seen
        vals = list(tree.item(iid, "values"))
        if idle > DEVICE_TTL:
            if vals[-1] != "Inactive":
                vals[-1] = "Inactive"
                tree.item(iid, values=tuple(vals), tags=("inactive",))
        else:
            if vals[-1] != "Active":
                vals[-1] = "Active"
                tree.item(iid, values=tuple(vals), tags=("",))

    # counters & progress
    active = sum(1 for mac in known_devices if time.time() - last_seen.get(mac, 0) <= DEVICE_TTL)
    count_var.set(f"Devices: {len(known_devices)}  •  Active: {active}")

    if scan_thread and scan_thread.is_alive():
        elapsed = int(time.time() - scan_start_time) if scan_start_time else 0
        status_var.set(f"Scanning… {elapsed}s")
    else:

        status_var.set("Scan stopped" if scan_start_time else "Ready to scan network")

    root.after(STATUS_REFRESH_MS, refresh_statuses)




def export_csv():
    if not known_devices:
        messagebox.showinfo("Export", "No devices to export yet.")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
        initialfile="network_devices.csv",
    )
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Type", "MAC", "Vendor", "IP", "Status", "Last Seen (epoch)"])
        for mac, iid in known_devices.items():
            vals = tree.item(iid, "values")
            w.writerow([*vals, int(last_seen.get(mac, 0))])
    status_var.set(f"Exported to {os.path.basename(path)}")


# =========================
# Scan controls
# =========================

def start_scan():
    global scan_thread, stop_event, scan_start_time

    if scan_thread and scan_thread.is_alive():
        return

    # Fresh state but keep rows to visualize live updates; if you want a full reset, uncomment below
    for child in tree.get_children(""):
        tree.delete(child)
    known_devices.clear()
    last_seen.clear()

    stop_event = threading.Event()
    scan_start_time = time.time()

    def runner():
        try:
            run_scan(on_new_device, stop_event)
        except Exception as e:
            q.put(("00:00:00:00:00:00", f"Scanner error: {e}", "—", time.time()))

    scan_thread = threading.Thread(target=runner, name="network-scan", daemon=True)
    scan_thread.start()

    start_btn.configure(state="disabled")
    stop_btn.configure(state="normal")


def stop_scan():
    global scan_thread
    try:
        if stop_event:
            stop_event.set()
    except Exception:
        pass

    start_btn.configure(state="normal")
    stop_btn.configure(state="disabled")


# Wire up buttons & events
start_btn.configure(command=start_scan)
stop_btn.configure(command=stop_scan)
export_btn.configure(command=export_csv)

tree.bind("<Button-3>", popup_menu)  # right-click

# Start background loops
root.after(QUEUE_POLL_MS, poll_queue)
root.after(STATUS_REFRESH_MS, refresh_statuses)

# Safety: stop scan when closing

def on_close():
    try:
        if stop_event:
            stop_event.set()
    except Exception:
        pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# 🚨 Remember: only scan networks you own or have permission for.
root.mainloop()
