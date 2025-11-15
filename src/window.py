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
stop_event = threading.Event()

# Track devices by MAC address
known_devices = {}

def on_new_device(mac, vendor, ip):
    q.put((mac, vendor, ip))

def poll_queue():
    try:
        while True:
            mac, vendor, ip = q.get_nowait()

            if mac in known_devices:
                # Update existing item if IP or vendor changed
                item_id = known_devices[mac]
                current_values = tree.item(item_id, "values")
                if current_values != (mac, vendor, ip):
                    tree.item(item_id, values=(mac, vendor, ip))
            else:
                # Add new device
                item_id = tree.insert("", "end", values=(mac, vendor, ip))
                known_devices[mac] = item_id

    except queue.Empty:
        pass
    # Re-enable Start when thread finishes
    if scan_thread and not scan_thread.is_alive():
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
    root.after(100, poll_queue)

def start_scan():
    global scan_thread, stop_event, known_devices
    
    # Clear previous data
    for item in tree.get_children():
        tree.delete(item)
    known_devices.clear()
    
    # Create new stop event for this scan
    stop_event = threading.Event()
    
    scan_thread = threading.Thread(
        target=run_scan,
        args=(on_new_device, stop_event),
        daemon=True,
    )
    scan_thread.start()
    start_btn.config(state="disabled")
    stop_btn.config(state="normal")

def stop_scan():
    if stop_event:
        stop_event.set()
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")

# ---- GUI ----
root = tk.Tk()
root.title("Network Scanner")
root.geometry("600x380")

columns = ("MAC", "Vendor", "IP")
tree = ttk.Treeview(root, columns=columns, show="headings")
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=190 if col == "Vendor" else 200, anchor="center")
tree.pack(fill="both", expand=True, padx=8, pady=(8, 4))

btns = ttk.Frame(root)
btns.pack(pady=6)
start_btn = ttk.Button(btns, text="Start Scan", command=start_scan)
stop_btn  = ttk.Button(btns, text="Stop Scan",  command=stop_scan)
start_btn.grid(row=0, column=0, padx=6)
stop_btn.grid(row=0, column=1, padx=6)
stop_btn.config(state="disabled")

poll_queue()
root.mainloop()
