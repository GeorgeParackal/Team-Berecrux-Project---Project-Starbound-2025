import threading
import queue
import tkinter as tk
from tkinter import ttk
from network_scan import run_scan

q = queue.Queue()
stop_event = threading.Event()
scan_thread = None

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

columns = ("MAC", "Vendor", "IP")
tree = ttk.Treeview(root, columns=columns, show="headings")
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=180 if col == "Vendor" else 170, anchor="center")

tree.pack(fill="both", expand=True)

button_frame = ttk.Frame(root)
button_frame.pack(pady=6)

start_button = ttk.Button(button_frame, text="Start Scan", command=start_scan)
start_button.pack(side="left", padx=5)

stop_button = ttk.Button(button_frame, text="Stop Scan", command=stop_scan, state="disabled")
stop_button.pack(side="left", padx=5)

poll_queue()
root.mainloop()
