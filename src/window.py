import threading, queue, tkinter as tk
from tkinter import ttk
import importlib, inspect, network_scan
import time

# Force-reload so we use the latest scanner code
importlib.reload(network_scan)
run_scan = network_scan.run_scan

q = queue.Queue()
scan_thread = None
stop_event = threading.Event()
known_devices = {}
scan_start_time = None

def on_new_device(mac, vendor, ip):
    q.put((mac, vendor, ip))

def update_progress():
    """Update progress bar during scan"""
    if scan_thread and scan_thread.is_alive():
        progress_bar['mode'] = 'indeterminate'
        progress_bar.start(10)
        elapsed = time.time() - scan_start_time if scan_start_time else 0
        status_label.config(text=f"Scanning network... ({elapsed:.0f}s)", foreground="#2E8B57")
    else:
        progress_bar.stop()
        progress_bar['mode'] = 'determinate'
        progress_bar['value'] = 0
        status_label.config(text="Scan stopped", foreground="#DC143C")

def poll_queue():
    try:
        while True:
            mac, vendor, ip = q.get_nowait()
            
            # Determine device type icon
            if "router" in vendor.lower() or "gateway" in vendor.lower():
                device_type = "🌐 Router"
            elif "apple" in vendor.lower():
                device_type = "🍎 Apple"
            elif "samsung" in vendor.lower():
                device_type = "📱 Samsung"
            else:
                device_type = "💻 Device"

            if mac in known_devices:
                item_id = known_devices[mac]
                current_values = tree.item(item_id, "values")
                if current_values != (device_type, mac, vendor, ip, "Active"):
                    tree.item(item_id, values=(device_type, mac, vendor, ip, "Active"))
            else:
                # Add new device - values: Type, MAC, Vendor, IP, Status
                item_id = tree.insert("", "end", values=(device_type, mac, vendor, ip, "Active"))
                known_devices[mac] = item_id

    except queue.Empty:
        pass
    
    # Keep scanning active - don't stop automatically
    root.after(100, poll_queue)

def start_scan():
    global scan_thread, stop_event, known_devices, scan_start_time
    
    # Clear previous data
    for item in tree.get_children():
        tree.delete(item)
    known_devices.clear()
    scan_start_time = time.time()
    
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
    update_progress()

def stop_scan():
    if stop_event:
        stop_event.set()
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")
    update_progress()

# ---- Professional GUI ----
root = tk.Tk()
root.title("Professional Network Scanner v2.0")
root.geometry("800x600")
root.configure(bg="#2C3E50")
root.resizable(True, True)

# Configure modern style
style = ttk.Style()
style.theme_use('clam')
style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#2C3E50', foreground='#ECF0F1')
style.configure('Header.TFrame', background='#34495E')
style.configure('Treeview', background='#ECF0F1', foreground='#2C3E50', fieldbackground='#ECF0F1')
style.configure('Treeview.Heading', background='#3498DB', foreground='white', font=('Arial', 10, 'bold'))
style.map('Treeview', background=[('selected', '#3498DB')])

# Header Frame
header_frame = ttk.Frame(root, style='Header.TFrame')
header_frame.pack(fill='x', padx=10, pady=(10, 5))

title_label = ttk.Label(header_frame, text="🔍 Network Device Scanner", style='Title.TLabel')
title_label.pack(pady=10)

# Main content frame
main_frame = ttk.Frame(root)
main_frame.pack(fill='both', expand=True, padx=10, pady=5)

# Device list with scrollbar
tree_frame = ttk.Frame(main_frame)
tree_frame.pack(fill='both', expand=True, pady=(0, 10))

columns = ("Type", "MAC Address", "Vendor", "IP Address", "Status")
tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

# Configure columns to match data order: Type, MAC, Vendor, IP, Status
tree.heading('Type', text='Device Type', anchor='center')
tree.column('Type', width=120, anchor='center')
tree.heading('MAC Address', text='MAC Address', anchor='center')
tree.column('MAC Address', width=150, anchor='center')
tree.heading('Vendor', text='Vendor/Manufacturer', anchor='center')
tree.column('Vendor', width=200, anchor='center')
tree.heading('IP Address', text='IP Address', anchor='center')
tree.column('IP Address', width=130, anchor='center')
tree.heading('Status', text='Status', anchor='center')
tree.column('Status', width=80, anchor='center')

# Scrollbar for treeview
scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)

tree.pack(side='left', fill='both', expand=True)
scrollbar.pack(side='right', fill='y')

# Control panel
control_frame = ttk.LabelFrame(main_frame, text="Scan Controls", padding=10)
control_frame.pack(fill='x', pady=(0, 10))

# Progress bar
progress_frame = ttk.Frame(control_frame)
progress_frame.pack(fill='x', pady=(0, 10))

progress_label = ttk.Label(progress_frame, text="Scan Progress:")
progress_label.pack(anchor='w')

progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
progress_bar.pack(fill='x', pady=(5, 0))

# Buttons
button_frame = ttk.Frame(control_frame)
button_frame.pack(fill='x')

start_btn = ttk.Button(button_frame, text="🚀 Start Network Scan", command=start_scan)
start_btn.pack(side='left', padx=(0, 10))

stop_btn = ttk.Button(button_frame, text="⏹️ Stop Scan", command=stop_scan, state='disabled')
stop_btn.pack(side='left', padx=(0, 10))

# Status bar
status_frame = ttk.Frame(root)
status_frame.pack(fill='x', side='bottom', padx=10, pady=(0, 10))

status_label = ttk.Label(status_frame, text="Ready to scan network", font=('Arial', 9))
status_label.pack(anchor='w')

device_count_label = ttk.Label(status_frame, text="Devices found: 0", font=('Arial', 9))
device_count_label.pack(anchor='e')

# Update device count and progress in status
def update_device_count():
    device_count_label.config(text=f"Devices found: {len(known_devices)}")
    if scan_thread and scan_thread.is_alive():
        update_progress()
    root.after(1000, update_device_count)

update_device_count()
poll_queue()
root.mainloop()
