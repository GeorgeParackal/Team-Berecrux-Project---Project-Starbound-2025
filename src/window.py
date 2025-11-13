import threading
import queue
import tkinter as tk
from tkinter import ttk
from network_scan import run_scan

q = queue.Queue()

def on_new_device(mac, vendor, ip):
    q.put((mac, vendor, ip))

def poll_queue():
    try:
        while True:
            mac, vendor, ip = q.get_nowait()
            tree.insert("", "end", values=(mac, vendor, ip))
    except queue.Empty:
        pass
    root.after(100, poll_queue)

def start_scan():
    threading.Thread(target=run_scan, args=(on_new_device,), daemon=True).start()
    start_button.config(state="disabled")

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

start_button = ttk.Button(root, text="Start Scan", command=start_scan)
start_button.pack(pady=6)

poll_queue()
root.mainloop()
