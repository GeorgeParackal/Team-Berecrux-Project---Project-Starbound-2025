import threading, queue, tkinter as tk
from tkinter import ttk
import importlib, inspect, network_scan

# Force-reload so we use the latest scanner code
importlib.reload(network_scan)
print("Using:", network_scan.__file__)
print("run_scan signature:", inspect.signature(network_scan.run_scan))
run_scan = network_scan.run_scan

q = queue.Queue()
scan_thread = None
scanned_devices = set()  # stores MAC addresses

def on_new_device(mac, vendor, ip):
    q.put((mac, vendor, ip))

def on_cycle_update(n: int):
    # safely update UI from thread
    root.after(0, lambda: cycle_label.config(text=f"Scan cycles: {n}"))

def poll_queue():
    try:
        while True:
            mac, vendor, ip = q.get_nowait()
            if mac in scanned_devices:
                continue
            scanned_devices.add(mac)
            index = len(tree.get_children()) + 1
            tree.insert("", "end", values=(index, mac, vendor, ip))
    except queue.Empty:
        pass
    # Re-enable Start when thread finishes
    if scan_thread and not scan_thread.is_alive():
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
    root.after(100, poll_queue)

def start_scan():
    global scan_thread
    stop_event.clear()
    scan_thread = threading.Thread(
        target=run_scan,
        args=(on_new_device, stop_event, on_cycle_update, 30),
        daemon=True
    )
    scan_thread.start()
    start_btn.config(state="disabled")
    stop_btn.config(state="normal")

def stop_scan():
    stop_event.set()
    start_button.config(state="normal")
    stop_button.config(state="disabled")
    cycle_label.config(text="Scan cycles: 0")

# ---- GUI ----
root = tk.Tk()
root.title("Network Scanner")
root.geometry("560x390")

COLUMNS_CONFIG = {
    "Index":  {"width": 40,  "anchor": "center"},
    "MAC":    {"width": 170, "anchor": "center"},
    "Vendor": {"width": 180, "anchor": "center"},
    "IP":     {"width": 170, "anchor": "center"},
}

columns = list(COLUMNS_CONFIG.keys())
tree = ttk.Treeview(root, columns=columns, show="headings")

for col, options in COLUMNS_CONFIG.items():
    tree.heading(col, text=col)
    tree.column(col, width=options["width"], anchor=options["anchor"])

tree.pack(fill="both", expand=True)

# Add scan cycle label
cycle_label = ttk.Label(root, text="Scan cycles: 0")
cycle_label.pack(pady=(4, 0))

button_frame = ttk.Frame(root)
button_frame.pack(pady=6)

start_button = ttk.Button(button_frame, text="Start Scan", command=start_scan)
start_button.pack(side="left", padx=5)

btns = ttk.Frame(root)
btns.pack(pady=6)
start_btn = ttk.Button(btns, text="Start Scan", command=start_scan)
stop_btn  = ttk.Button(btns, text="Stop Scan",  command=stop_scan)
start_btn.grid(row=0, column=0, padx=6)
stop_btn.grid(row=0, column=1, padx=6)
stop_btn.config(state="disabled")

poll_queue()
root.mainloop()
