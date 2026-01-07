import customtkinter as ctk
import threading
import network_scan as ns
import csv
from tkinter import filedialog, messagebox

#=========Globals for thrread============
stop_event = None
scan_thread = None
table_rows = []  # holds (name, mac, vendor, ip)
device_counter = 0

def generate_device_name():
    global device_counter
    device_counter += 1
    return f"device_{device_counter}"

def export_csv():
    if not table_rows:
        messagebox.showinfo("Export CSV", "No data to export.")
        return
    path = filedialog.asksaveasfilename(
        title="Save scan results",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile="scan_results.csv",
    )
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Name", "Mac", "Vendor", "IP"])
            for row in table_rows:
                w.writerow([row['name'], row['mac'], row['vendor'], row['ip']]) #export doesnt work
            #w.writerows([table_rows]) #export doesnt work
        messagebox.showinfo("Export CSV", f"Saved to:\n{path}")
    except Exception as e:
        messagebox.showerror("Export CSV", f"Failed to save:\n{e}")


# ================== configs =================
ctk.set_appearance_mode("dark")

App_title = "Network Scanner version 1.0"
App_geometry = "600x900"
Background_color = "#1f2937"
panel_color = "#374151"
button_color = "#3b82f6"
#=============================================

#===================Initialize App============
app = ctk.CTk()
app.title(App_title)
app.geometry(App_geometry)
app.resizable(False, False)
app.configure(fg_color=Background_color)
app.grid_columnconfigure(0, weight=1)
#=============================================

# ================Header ====================
header = ctk.CTkFrame(app, fg_color=Background_color)
header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
header.grid_columnconfigure(0, weight=1)

title = ctk.CTkLabel(header, text="Network Device Scanner",font=ctk.CTkFont(size=28, weight="bold"))
subtitle = ctk.CTkLabel(header, text="Version 1.0 Offline Scanner - Designed for proof of concept",font=ctk.CTkFont(size=13))
title.grid(row=0, column=0, sticky="ew", pady=(0,2))
subtitle.grid(row=1, column=0, sticky="ew")
#=============================================

# =====Toolbar================================
toolbar = ctk.CTkFrame(app, fg_color=panel_color, corner_radius=6)
toolbar.grid(row=1, column=0, sticky="ew", padx=14, pady=6)

btn_start = ctk.CTkButton(toolbar, text="Start Scan", fg_color=button_color, hover_color="#000000")
btn_stop  = ctk.CTkButton(toolbar, text="Stop Scan", state="disabled")
btn_csv   = ctk.CTkButton(toolbar, text="Export CSV", fg_color=button_color, hover_color="#000000", command=export_csv)

btn_start.grid(row=0, column=0, padx=(12, 8), pady=12)
btn_stop.grid (row=0, column=1, padx=8, pady=12)
btn_csv.grid  (row=0, column=2, padx=8, pady=12)
#=============================================

# =====Main-Body================================
mainbody = ctk.CTkFrame(app, fg_color=panel_color, corner_radius=6)
mainbody.grid(row=2, column=0, sticky="nsew", padx=14, pady=6)
app.grid_rowconfigure(2, weight=1)
#=============================================

# =====Footer===============================
status = ctk.CTkFrame(app, fg_color=panel_color, corner_radius=6)
status.grid(row=3, column=0, sticky="ew", padx=14, pady=6)

status_label = ctk.CTkLabel(status, text="Devices: 0 • Active: 0", text_color="#9ca3af")
status_label.pack(anchor="e", padx=10, pady=6)

# spinner beside the status text
status_label.pack_forget()
status_label.pack(side="right", padx=(6, 6), pady=6)

spinner = ctk.CTkProgressBar(status, mode="indeterminate", width=100)
spinner.pack(side="right", padx=(6, 10), pady=6)
spinner.stop()
spinner.pack_forget()

#=============================================


# ================= CTK-only "table" (no ttk) ====================
# Layout: [header row] + [scrollable rows]

# --- header row ---
table_header = ctk.CTkFrame(mainbody, fg_color=panel_color)
table_header.pack(fill="x", padx=10, pady=(10, 0))

headers = ["Name", "Mac", "Vendor", "IP"]
col_weights = [30, 35, 35, 30]  # relative widths; tweak to taste

for i, (h, w) in enumerate(zip(headers, col_weights)):
    table_header.grid_columnconfigure(i, weight=w)
    ctk.CTkLabel(
        table_header, text=h, anchor="center",
        font=ctk.CTkFont(size=12, weight="bold"),
        fg_color="#4b5563"  # slightly lighter bar for header
    ).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 4), pady=(4, 4))


# --- scrollable body for rows ---
table_body = ctk.CTkScrollableFrame(mainbody, fg_color=panel_color, corner_radius=6)
table_body.pack(fill="both", expand=True, padx=10, pady=(6, 10))

# grid weights for the scrollable frame (same proportions as header)
for i, w in enumerate(col_weights):
    table_body.grid_columnconfigure(i, weight=w)

# helpers to manage rows
_row_iid = 0
def clear_rows():
    for child in table_body.winfo_children():
        child.destroy()
    global _row_iid
    _row_iid = 0
    table_rows.clear()  # clear CSV data

def insert_row(values): #takes in device name, mac, vendor, ip
    global _row_iid

    row_data = {
        'name': values[0],
        'mac': values[1], 
        'vendor': values[2],
        'ip': values[3]
    }
    
    pads = dict(padx=(0, 4), pady=(2, 2), sticky="ew")

    #making the name column editable
    name_entry = ctk.CTkEntry(table_body)
    name_entry.insert(0, values[0])
    name_entry.grid(row=_row_iid, column=0, **pads)

    def on_name_change(event, data = row_data, entry = name_entry):
        data['name'] = entry.get()

    name_entry.bind("<FocusOut>", on_name_change)
    name_entry.bind("<Return>", on_name_change)

    # one label per column, centered; you can change anchor="w" to left-align
    ctk.CTkLabel(table_body, text=values[1], anchor="center").grid(row=_row_iid, column=1, **pads)
    ctk.CTkLabel(table_body, text=values[2], anchor="center").grid(row=_row_iid, column=2, **pads)
    ctk.CTkLabel(table_body, text=values[3], anchor="center").grid(row=_row_iid, column=3, **pads)
    _row_iid += 1
    table_rows.append(tuple(values))  # save row for CSV
    #table_rows.append(tuple(row_data))  # save row for CSV



# ================= scan wiring (thread + callback) =================
seen = set()
counts = {"devices": 0, "active": 0}

def _update_status():
    status_label.configure(text=f"Devices: {counts['devices']} • Active: {counts['active']}")



def _spinner_on():
    spinner.pack(side="right", padx=(6, 10), pady=6)
    spinner.start()

def _spinner_off():
    spinner.stop()
    spinner.pack_forget()


def scan_callback(a, b, c):
    # ("error","scan_failed", msg) OR (mac, vendor, ip)
    if a == "error":
        app.after(0, lambda: status_label.configure(text=f"Error: {c}"))
        return
    mac, vendor, ip = a, b, c
    if mac in seen:
        return
    seen.add(mac)

    def ui_insert():
        counts["devices"] += 1
        counts["active"] += 1
        insert_row((generate_device_name(), mac, vendor, ip))
        _update_status()
    app.after(0, ui_insert)

def start_scan():
    _spinner_on()
    global stop_event, scan_thread
    if scan_thread and scan_thread.is_alive():
        return
    global device_counter
    device_counter = 0
    # reset table + counters
    clear_rows()
    seen.clear()
    counts["devices"] = counts["active"] = 0
    _update_status()

    btn_start.configure(state="disabled")
    btn_stop.configure(state="normal")

    stop_event = threading.Event()
    scan_thread = threading.Thread(
        target=ns.run_scan,
        kwargs={"callback": scan_callback, "stop_event": stop_event, "interval": 15},
        daemon=True,
    )
    scan_thread.start()

def stop_scan():
    _spinner_off()
    global stop_event
    if stop_event:
        stop_event.set()
    btn_start.configure(state="normal")
    btn_stop.configure(state="disabled")

def on_close():
    _spinner_off()
    if stop_event:
        stop_event.set()
    app.after(50, app.destroy)

btn_start.configure(command=start_scan)
btn_stop.configure(command=stop_scan)
app.protocol("WM_DELETE_WINDOW", on_close)
# ================= end append block =================

app.mainloop()

