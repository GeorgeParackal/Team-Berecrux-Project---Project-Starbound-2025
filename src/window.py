import threading
import queue
import tkinter as tk
from tkinter import ttk
from network_scan import run_scanmenu 
q = queue.Queue()
stop_event = threading.Event()
scan_thread = None
scanned_devices = set()  # stores MAC addresses

def on_new_device(mac, vendor, ip):
    q.put((mac, vendor, ip))

def poll_queue():
    try:
        while True:
            mac, vendor, ip = q.get_nowait()
            
            # Skip if we've already seen this device
            if mac in scanned_devices:
                continue
            
            scanned_devices.add(mac)  # remember this device
            
            # Add visual index
            index = len(tree.get_children()) + 1
            tree.insert("", "end", values=(index, mac, vendor, ip))
            
    except queue.Empty:
        pass
    
    root.after(100, poll_queue)

def start_scan():
    global scan_thread
    stop_event.clear()
    scan_thread = threading.Thread(target=run_scan, args=(on_new_device, stop_event), daemon=True)
    scan_thread.start()
    start_button.config(state="disabled")
    stop_button.config(state="normal")

def stop_scan():
    stop_event.set()
    start_button.config(state="normal")
    stop_button.config(state="disabled")

# ---- GUI ----
root = tk.Tk()
root.title("Network Scanner")
root.geometry("560x360")

COLUMNS_CONFIG = {
    "Index":  {"width": 40,  "anchor": "center"},
    "MAC":    {"width": 170, "anchor": "center"},
    "Vendor": {"width": 180, "anchor": "center"},
    "IP":     {"width": 170, "anchor": "center"},
}

columns = list(COLUMNS_CONFIG.keys())
tree = ttk.Treeview(root, columns=columns, show="headings")

# Build columns dynamically from config
for col, options in COLUMNS_CONFIG.items():
    tree.heading(col, text=col)
    tree.column(col, width=options["width"], anchor=options["anchor"])

tree.pack(fill="both", expand=True)

button_frame = ttk.Frame(root)
button_frame.pack(pady=6)

start_button = ttk.Button(button_frame, text="Start Scan", command=start_scan)
start_button.pack(side="left", padx=5)

stop_button = ttk.Button(button_frame, text="Stop Scan", command=stop_scan, state="disabled")
stop_button.pack(side="left", padx=5)

poll_queue()
root.mainloop()
