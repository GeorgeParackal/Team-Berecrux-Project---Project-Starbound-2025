import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import importlib
import inspect
import time
import csv
import os
import sys
import json
import math

# =========================
# CONFIG
# =========================
APP_TITLE = "🔍 Network Device Scanner"
BG_DARK = "#111827"  # slate-900
CARD = "#1f2937"     # slate-800
ACCENT = "#2563eb"   # blue-600
ACCENT_HOVER = "#1d4ed8"  # blue-700
TEXT = "#e5e7eb"     # gray-200
TEXT_MUTED = "#9ca3af"  # gray-400
SUCCESS = "#22c55e"  # green-500
DANGER = "#ef4444"   # red-500
WARNING = "#f59e0b"  # amber-500
ROW_ALT = "#111827"

DEVICE_TTL = 60  # seconds of inactivity before a device is marked inactive
QUEUE_POLL_MS = 100
STATUS_REFRESH_MS = 1000

# Visualization colors for device types
TYPE_COLORS = {
    "🌐 Router": "#22d3ee",   # cyan-400
    "🍎 Apple": "#f472b6",    # pink-400
    "📱 Samsung": "#34d399",  # green-400
    "🧪 Raspberry Pi": "#f59e0b",  # amber-500
    "💻 Device": "#a78bfa",   # violet-400
    "🔧 Device": "#60a5fa",   # blue-400
}

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

sorted_col = None


def _update_sorted_heading(tree, col, reverse):
    global sorted_col
    # Reset all headings
    for c in tree["columns"]:
        label = c
        if c == col:
            label = f"{c} {'▼' if reverse else '▲'}"
        tree.heading(c, text=label, command=lambda cc=c: sort_by_column(tree, cc))
    sorted_col = col


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
    _update_sorted_heading(tree, col, reverse)


# Filter helpers
filter_var = None


def matches_filter(values):
    needle = (filter_var.get() or "").strip().lower()
    if not needle:
        return True
    return any(needle in str(v).lower() for v in values)


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

# --- Controls Card ---
controls_card = ttk.Frame(root, style="Card.TFrame", padding=14)
controls_card.pack(fill="x", padx=16, pady=8)

btn_frame = ttk.Frame(controls_card, style="Card.TFrame")
btn_frame.pack(side="left")

start_btn = ttk.Button(btn_frame, text="🚀  Start Scan", style="Accent.TButton")
stop_btn = ttk.Button(btn_frame, text="⏹️  Stop Scan", style="Danger.TButton", state="disabled")
export_btn = ttk.Button(btn_frame, text="💾  Export CSV")
export_json_btn = ttk.Button(btn_frame, text="🧾  Export JSON")
settings_btn = ttk.Button(btn_frame, text="⚙  Settings")

start_btn.grid(row=0, column=0, padx=(0, 8))
stop_btn.grid(row=0, column=1, padx=8)
export_btn.grid(row=0, column=2, padx=8)
export_json_btn.grid(row=0, column=3, padx=8)
settings_btn.grid(row=0, column=4, padx=8)
progress = ttk.Progressbar(btn_frame, mode="determinate", length=160)
progress.grid(row=0, column=5, padx=(12,4))
scan_time_var = tk.StringVar(value="00:00")
scan_time_lbl = ttk.Label(btn_frame, textvariable=scan_time_var, style="Sub.TLabel")
scan_time_lbl.grid(row=0, column=6, padx=(4,0))

# Filter/search
filter_frame = ttk.Frame(controls_card, style="Card.TFrame")
filter_frame.pack(side="right")

filter_var = tk.StringVar()
filter_entry = ttk.Entry(filter_frame, textvariable=filter_var, width=32)
filter_entry.grid(row=0, column=0, padx=(0, 8))
clear_filter_btn = ttk.Button(filter_frame, text="✖", width=3)
clear_filter_btn.grid(row=0, column=1)

# --- Tree + Insights Card (split) ---
list_card = ttk.Frame(root, style="Card.TFrame", padding=12)
list_card.pack(fill="both", expand=True, padx=16, pady=(8, 16))

main_split = ttk.Frame(list_card, style="Card.TFrame")
main_split.pack(fill="both", expand=True)

# Left: table
table_frame = ttk.Frame(main_split, style="Card.TFrame")
table_frame.pack(side="left", fill="both", expand=True)

columns = ("Type", "MAC Address", "Vendor", "IP Address", "Status")
tree = ttk.Treeview(table_frame, columns=columns, show="headings")

# Configure columns
col_specs = {
    "Type": dict(width=140, anchor="center"),
    "MAC Address": dict(width=170, anchor="center"),
    "Vendor": dict(width=260, anchor="center"),  # centered vendor values
    "IP Address": dict(width=150, anchor="center"),
    "Status": dict(width=100, anchor="center"),
}

for col in columns:
    tree.heading(col, text=col, anchor="center", command=lambda c=col: sort_by_column(tree, c))
    tree.column(col, **col_specs[col])

# Scrollbar
scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)

# Layout
tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Row tags for styling
tree.tag_configure("inactive", foreground=TEXT_MUTED)
tree.tag_configure("alt", background=ROW_ALT)
# Highlight for filter matches
try:
    tree.tag_configure("match", background=ACCENT, foreground="white")
except Exception:
    pass

# Right: insights & details
side_panel = ttk.Frame(main_split, style="Card.TFrame")
side_panel.pack(side="left", fill="y", padx=(12, 0))

insights_title = ttk.Label(side_panel, text="Network Insights", style="Info.TLabel")
insights_title.pack(anchor="w")

chart_canvas = tk.Canvas(side_panel, width=220, height=220, bg=CARD, highlightthickness=0)
chart_canvas.pack(pady=(8, 12))

stats_frame = ttk.Frame(side_panel, style="Card.TFrame")
stats_frame.pack(fill="x")

stat_total = tk.StringVar(value="Total: 0")
stat_active = tk.StringVar(value="Active: 0")
stat_inactive = tk.StringVar(value="Inactive: 0")
stat_vendors = tk.StringVar(value="Vendors: 0")

ttk.Label(stats_frame, textvariable=stat_total, style="Info.TLabel").pack(anchor="w")
ttk.Label(stats_frame, textvariable=stat_active, style="Info.TLabel").pack(anchor="w")
ttk.Label(stats_frame, textvariable=stat_inactive, style="Info.TLabel").pack(anchor="w")
ttk.Label(stats_frame, textvariable=stat_vendors, style="Info.TLabel").pack(anchor="w")

ttk.Separator(side_panel, orient="horizontal").pack(fill="x", pady=12)

details_title = ttk.Label(side_panel, text="Selection Details", style="Info.TLabel")
details_title.pack(anchor="w")

sel_mac = tk.StringVar(value="—")
sel_ip = tk.StringVar(value="—")
sel_vendor = tk.StringVar(value="—")
sel_type = tk.StringVar(value="—")
sel_status = tk.StringVar(value="—")
sel_seen = tk.StringVar(value="—")

def _kv(parent, key, var):
    row = ttk.Frame(parent, style="Card.TFrame")
    row.pack(fill="x", pady=1)
    ttk.Label(row, text=f"{key}:", style="Info.TLabel").pack(side="left")
    ttk.Label(row, textvariable=var, style="Info.TLabel").pack(side="right")

details_frame = ttk.Frame(side_panel, style="Card.TFrame")
details_frame.pack(fill="x", pady=(6, 8))

_kv(details_frame, "Type", sel_type)
_kv(details_frame, "MAC", sel_mac)
_kv(details_frame, "Vendor", sel_vendor)
_kv(details_frame, "IP", sel_ip)
_kv(details_frame, "Status", sel_status)
_kv(details_frame, "Last Seen", sel_seen)

actions_frame = ttk.Frame(side_panel, style="Card.TFrame")
actions_frame.pack(fill="x")
btn_ping = ttk.Button(actions_frame, text="📡 Ping", style="Accent.TButton")
btn_copy_mac = ttk.Button(actions_frame, text="Copy MAC")
btn_copy_ip = ttk.Button(actions_frame, text="Copy IP")
btn_ping.grid(row=0, column=0, padx=(0, 6), pady=2)
btn_copy_mac.grid(row=0, column=1, padx=6, pady=2)
btn_copy_ip.grid(row=0, column=2, padx=6, pady=2)

# --- Status Bar ---
status = ttk.Frame(root, style="TFrame")
status.pack(fill="x", padx=16, pady=(0, 12))

status_var = tk.StringVar(value="")
count_var = tk.StringVar(value="")  # Hidden per request (removed bottom-right device count)

# Removed status label and count label per request

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

def compute_stats():
    now = time.time()
    total = len(known_devices)
    active = sum(1 for mac in known_devices if now - last_seen.get(mac, 0) <= DEVICE_TTL)
    inactive = total - active
    vendors = set()
    dist = {}
    for mac, iid in known_devices.items():
        vals = tree.item(iid, "values")
        vendors.add(vals[2])
        t = vals[0]
        dist[t] = dist.get(t, 0) + 1
    return total, active, inactive, len(vendors), dist


def draw_donut(canvas, distribution):
    canvas.delete("all")
    total = sum(distribution.values())
    if total == 0:
        # Empty placeholder donut
        canvas.create_oval(10, 10, 210, 210, outline=TEXT_MUTED, width=2)
        canvas.create_text(110, 110, text="No data", fill=TEXT_MUTED, font=("Segoe UI", 10, "bold"))
        return
    start = -90  # start at top
    bbox = (10, 10, 210, 210)
    for label, count in distribution.items():
        extent = 360 * (count / total)
        color = TYPE_COLORS.get(label, "#64748b")
        canvas.create_arc(bbox, start=start, extent=extent, style=tk.PIESLICE, outline=CARD, width=1, fill=color)
        start += extent
    # inner cut-out for donut effect
    canvas.create_oval(55, 55, 165, 165, fill=CARD, outline=CARD)


def update_insights():
    total, active, inactive, vendors_count, dist = compute_stats()
    stat_total.set(f"Total: {total}")
    stat_active.set(f"Active: {active}")
    stat_inactive.set(f"Inactive: {inactive}")
    stat_vendors.set(f"Vendors: {vendors_count}")
    draw_donut(chart_canvas, dist)


def on_select(event=None):
    sel = tree.selection()
    if not sel:
        sel_mac.set("—"); sel_ip.set("—"); sel_vendor.set("—"); sel_type.set("—"); sel_status.set("—"); sel_seen.set("—")
        return
    iid = sel[0]
    vals = tree.item(iid, "values")
    mac = vals[1]; vendor = vals[2]; ip = vals[3]; status_txt = vals[4]; typ = vals[0]
    seen_epoch = last_seen.get(mac, 0)
    sel_mac.set(mac)
    sel_vendor.set(vendor)
    sel_ip.set(ip)
    sel_status.set(status_txt)
    sel_type.set(typ)
    sel_seen.set(time.strftime('%H:%M:%S', time.localtime(seen_epoch)) if seen_epoch else "—")

def copy_col(idx):
    sel = tree.selection()
    if not sel:
        return
    values = tree.item(sel[0], "values")
    try:
        root.clipboard_clear()
        root.clipboard_append(values[idx])
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

    # Re-apply filter on the fly
    apply_filter()
    update_insights()

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
        progress.configure(mode="indeterminate")
        progress.start(12)
        elapsed = int(time.time() - scan_start_time) if scan_start_time else 0
        # Update mm:ss elapsed timer next to progress bar
        minutes = elapsed // 60
        seconds = elapsed % 60
        scan_time_var.set(f"{minutes:02d}:{seconds:02d}")
    else:
        progress.stop()
        progress.configure(mode="determinate", value=0)

    update_insights()
    root.after(STATUS_REFRESH_MS, refresh_statuses)



def apply_filter(*_):
    # Hide non-matching devices; restore them when filter is cleared
    needle = (filter_var.get() or "").strip().lower()
    all_items = list(known_devices.values())
    
    if not needle:
        # Restore all devices and fix alt row striping
        for idx, iid in enumerate(all_items):
            try:
                tree.reattach(iid, "", "end")
            except tk.TclError:
                pass
            tags = [t for t in tree.item(iid, "tags") if t not in ("match", "alt")]
            if idx % 2 == 1:
                tags.append("alt")
            tree.item(iid, tags=tuple(tags))
        return

    # Show only matches; hide non-matches
    visible_idx = 0
    for iid in all_items:
        vals = tree.item(iid, "values")
        joined = " ".join(str(v).lower() for v in vals)
        if needle in joined:
            try:
                tree.reattach(iid, "", "end")
            except tk.TclError:
                pass
            tags = [t for t in tree.item(iid, "tags") if t not in ("match", "alt")]
            if visible_idx % 2 == 1:
                tags.append("alt")
            tree.item(iid, tags=tuple(tags))
            visible_idx += 1
        else:
            try:
                tree.detach(iid)
            except tk.TclError:
                pass



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


def export_json():
    data = []
    for mac, iid in known_devices.items():
        vals = tree.item(iid, "values")
        data.append({
            "type": vals[0],
            "mac": vals[1],
            "vendor": vals[2],
            "ip": vals[3],
            "status": vals[4],
            "last_seen": int(last_seen.get(mac, 0)),
        })
    path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON", "*.json")],
        initialfile="network_devices.json",
    )
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"devices": data, "generated_at": int(time.time())}, f, indent=2)


def open_settings():
    dlg = tk.Toplevel(root)
    dlg.title("Settings")
    dlg.configure(bg=CARD)
    dlg.resizable(False, False)
    ttk.Label(dlg, text="Device Inactivity TTL (seconds)", style="Info.TLabel").pack(padx=12, pady=(12, 4))
    ttl_var = tk.IntVar(value=DEVICE_TTL)
    ttl_scale = ttk.Scale(dlg, from_=10, to=300, orient="horizontal")
    ttl_scale.set(DEVICE_TTL)
    ttl_scale.pack(fill="x", padx=12)

    def save_and_close():
        global DEVICE_TTL
        DEVICE_TTL = int(ttl_scale.get())
        dlg.destroy()

    btns = ttk.Frame(dlg, style="Card.TFrame")
    btns.pack(fill="x", padx=12, pady=12)
    ttk.Button(btns, text="Save", style="Accent.TButton", command=save_and_close).pack(side="right")
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=(0, 8))


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
    scan_time_var.set("00:00")  # reset timer display on new scan

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
export_json_btn.configure(command=export_json)
settings_btn.configure(command=open_settings)
clear_filter_btn.configure(command=lambda: (filter_var.set(""), apply_filter()))
filter_var.trace_add("write", lambda *_: apply_filter())

tree.bind("<Button-3>", popup_menu)  # right-click
tree.bind("<<TreeviewSelect>>", on_select)
btn_ping.configure(command=ping_selected)
btn_copy_mac.configure(command=lambda: copy_col(1))
btn_copy_ip.configure(command=lambda: copy_col(3))

# Keyboard shortcuts
root.bind("<Control-f>", lambda e: (filter_entry.focus_set(), filter_entry.select_range(0, tk.END)))
root.bind("<Control-s>", lambda e: export_csv())
root.bind("<F5>", lambda e: start_scan())
root.bind("<Shift-F5>", lambda e: stop_scan())

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
