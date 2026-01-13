import customtkinter as ctk
import threading
import network_scan as ns
import csv
import json
import os
import hashlib
from tkinter import filedialog, messagebox, simpledialog

#=========Globals for thread============
stop_event = None
scan_thread = None
table_rows = []  # holds (mac, vendor, ip, network)
protected_networks = {}
current_networks = []

def load_protected_networks():
    """Load password-protected networks from file"""
    global protected_networks
    if os.path.exists("protected_networks.json"):
        with open("protected_networks.json", 'r') as f:
            protected_networks = json.load(f)
    return protected_networks

def save_protected_networks():
    """Save protected networks to file"""
    with open("protected_networks.json", 'w') as f:
        json.dump(protected_networks, f, indent=2)

def hash_password(password):
    """Hash password for storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def show_security_info():
    """Show security information about password protection"""
    info = """🔒 SECURITY INFORMATION 🔒

⚠️ IMPORTANT LIMITATIONS ⚠️

Password protection is LOCAL ONLY:
• Only protects THIS device/installation
• Other devices with this program can scan freely
• Protection is stored in 'protected_networks.json'
• Deleting the file removes ALL protection

🔄 PASSWORD RESET:
• Use '🔓 Reset Password' button
• Completely removes protection
• Network becomes scannable by anyone

🌐 NETWORK-LEVEL SECURITY:
For real protection, configure your router:
• Disable network discovery
• Enable MAC address filtering
• Use strong WiFi passwords
• Enable firewall rules

🚨 This tool's password protection is for workflow management, NOT network security!"""
    
    messagebox.showinfo("Security Information", info)

def show_disclaimer():
    """Show legal disclaimer"""
    disclaimer = """⚠️ LEGAL DISCLAIMER ⚠️

This network scanner should ONLY be used on:
• Networks you own
• Networks you have explicit permission to scan
• Your home/personal networks

UNAUTHORIZED NETWORK SCANNING IS ILLEGAL

By clicking 'OK', you confirm:
✓ You own or have permission to scan target networks
✓ You will not use this tool for malicious purposes
✓ You understand legal consequences of unauthorized scanning

For unknown/protected devices:
• Router manufacturers may not share device names for privacy
• Some devices intentionally hide their identity for security"""
    
    result = messagebox.askokcancel("Legal Disclaimer", disclaimer)
    if not result:
        app.quit()
        return False
    return True

def check_network_access(network_range):
    """Check if network requires password"""
    if network_range in protected_networks:
        password = simpledialog.askstring(
            "Protected Network", 
            f"Network {network_range} is password protected.\nEnter password:",
            show='*'
        )
        if not password:
            return False
        
        hashed = hash_password(password)
        if hashed != protected_networks[network_range]:
            messagebox.showerror("Access Denied", "Incorrect password!")
            return False
    return True

def protect_network():
    """Add password protection to a network"""
    network = simpledialog.askstring("Protect Network", "Enter network range (e.g., 192.168.1.0/24):")
    if not network:
        return
    
    password = simpledialog.askstring("Set Password", "Enter protection password:", show='*')
    if not password:
        return
    
    confirm = simpledialog.askstring("Confirm Password", "Confirm password:", show='*')
    if password != confirm:
        messagebox.showerror("Error", "Passwords don't match!")
        return
    
    protected_networks[network] = hash_password(password)
    save_protected_networks()
    messagebox.showinfo("Success", f"Network {network} is now protected!")

def reset_network_password():
    """Reset password for a protected network"""
    if not protected_networks:
        messagebox.showinfo("No Protected Networks", "No networks are currently protected.")
        return
    
    # Show list of protected networks
    network_list = "\n".join([f"• {net}" for net in protected_networks.keys()])
    network = simpledialog.askstring(
        "Reset Network Password", 
        f"Protected networks:\n{network_list}\n\nEnter network to reset password:"
    )
    
    if not network or network not in protected_networks:
        messagebox.showerror("Error", "Network not found in protected list!")
        return
    
    # Confirm reset
    confirm = messagebox.askyesno(
        "Confirm Reset", 
        f"⚠️ WARNING ⚠️\n\nThis will REMOVE password protection from:\n{network}\n\nAnyone can scan this network after reset!\n\nContinue?"
    )
    
    if confirm:
        del protected_networks[network]
        save_protected_networks()
        messagebox.showinfo("Password Reset", f"Password protection removed from {network}\n\n⚠️ Network is now unprotected!")

def get_network_ranges():
    """Get multiple network ranges to scan"""
    networks = []
    
    # Default current network
    try:
        import get_local_ip_address as host_ip
        from ipaddress import IPv4Interface
        host_ip_address = host_ip.get_local_ip_address()
        default_network = str(IPv4Interface(host_ip_address + '/24').network)
        networks.append(default_network)
    except:
        pass
    
    # Ask for additional networks
    while True:
        network = simpledialog.askstring(
            "Multi-Network Scan", 
            f"Current networks: {networks}\n\nAdd another network range? (e.g., 192.168.2.0/24)\nLeave empty to start scan:"
        )
        if not network:
            break
        
        # Check access permission
        if check_network_access(network):
            networks.append(network)
        else:
            messagebox.showwarning("Access Denied", f"Cannot scan protected network: {network}")
    
    return networks

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
            w.writerow(["Mac", "Vendor", "IP", "Network"])
            w.writerows(table_rows)
        messagebox.showinfo("Export CSV", f"Saved to:\n{path}")
    except Exception as e:
        messagebox.showerror("Export CSV", f"Failed to save:\n{e}")


# ================== configs =================
ctk.set_appearance_mode("dark")

App_title = "Multi-Network Scanner Pro v2.1"
App_geometry = "975x900"
Background_color = "#1f2937"
panel_color = "#374151"
button_color = "#3b82f6"
#=============================================

#===================Initialize App============
load_protected_networks()  # Load protected networks on startup

app = ctk.CTk()
app.title(App_title)
app.geometry(App_geometry)
app.resizable(False, False)
app.configure(fg_color=Background_color)
app.grid_columnconfigure(0, weight=1)

# Show disclaimer on startup
app.after(100, show_disclaimer)
#=============================================

# ================Header ====================
header = ctk.CTkFrame(app, fg_color=Background_color)
header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
header.grid_columnconfigure(0, weight=1)

title = ctk.CTkLabel(header, text="🔍 Multi-Network Scanner Pro",font=ctk.CTkFont(size=28, weight="bold"))
subtitle = ctk.CTkLabel(header, text="Version 2.1 - Multi-Network Support with Password Protection",font=ctk.CTkFont(size=13))
title.grid(row=0, column=0, sticky="ew", pady=(0,2))
subtitle.grid(row=1, column=0, sticky="ew")
#=============================================

# =====Toolbar================================
toolbar = ctk.CTkFrame(app, fg_color=panel_color, corner_radius=6)
toolbar.grid(row=1, column=0, sticky="ew", padx=14, pady=6)

btn_start = ctk.CTkButton(toolbar, text="🚀 Start Multi-Scan", fg_color=button_color, hover_color="#000000")
btn_stop  = ctk.CTkButton(toolbar, text="⏹️ Stop Scan", state="disabled")
btn_protect = ctk.CTkButton(toolbar, text="🔒 Protect Network", fg_color="#dc2626", hover_color="#b91c1c", command=protect_network)
btn_reset = ctk.CTkButton(toolbar, text="🔓 Reset Password", fg_color="#f59e0b", hover_color="#d97706", command=reset_network_password)
btn_csv   = ctk.CTkButton(toolbar, text="📄 Export CSV", fg_color=button_color, hover_color="#000000", command=export_csv)

btn_info = ctk.CTkButton(toolbar, text="ℹ️ Security Info", fg_color="#6b7280", hover_color="#4b5563", command=show_security_info)

btn_start.grid(row=0, column=0, padx=(12, 6), pady=12)
btn_stop.grid (row=0, column=1, padx=6, pady=12)
btn_protect.grid(row=0, column=2, padx=6, pady=12)
btn_reset.grid(row=0, column=3, padx=6, pady=12)
btn_info.grid(row=0, column=4, padx=6, pady=12)
btn_csv.grid  (row=0, column=5, padx=6, pady=12)
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

headers = ["Mac", "Vendor", "IP", "Network"]
col_weights = [25, 30, 25, 20]  # relative widths; tweak to taste

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


def insert_row(values):
    global _row_iid
    pads = dict(padx=(0, 4), pady=(2, 2), sticky="ew")
    # one label per column, centered; you can change anchor="w" to left-align
    ctk.CTkLabel(table_body, text=values[0], anchor="center").grid(row=_row_iid, column=0, **pads)
    ctk.CTkLabel(table_body, text=values[1], anchor="center").grid(row=_row_iid, column=1, **pads)
    ctk.CTkLabel(table_body, text=values[2], anchor="center").grid(row=_row_iid, column=2, **pads)
    ctk.CTkLabel(table_body, text=values[3], anchor="center").grid(row=_row_iid, column=3, **pads)
    _row_iid += 1
    table_rows.append(tuple(values))  # save row for CSV


# ================= scan wiring (thread + callback) =================
seen = set()
counts = {"devices": 0, "active": 0}
protected_popup_shown = False  # Flag to show popup only once

def _update_status():
    status_label.configure(text=f"Devices: {counts['devices']} • Active: {counts['active']}")

def _spinner_on():
    spinner.pack(side="right", padx=(6, 10), pady=6)
    spinner.start()

def _spinner_off():
    spinner.stop()
    spinner.pack_forget()

def scan_callback(a, b, c, network="Unknown"):
    # ("error","scan_failed", msg) OR (mac, vendor, ip)
    if a == "error":
        app.after(0, lambda: status_label.configure(text=f"Error: {c}"))
        return
    mac, vendor, ip = a, b, c
    
    # Privacy protection for unknown devices
    global protected_popup_shown
    if vendor.lower() in ['unknown', '', 'n/a']:
        vendor = "🔒 Protected Identity"
        # Show explanation popup only once per scan session
        if not protected_popup_shown:
            protected_popup_shown = True
            app.after(0, lambda: messagebox.showinfo(
                "Protected Devices Detected",
                f"Some devices show as 'Protected Identity' because:\n\n"
                f"• Device manufacturer is unknown/hidden\n"
                f"• Router may be protecting device privacy\n"
                f"• Device intentionally hides its identity\n"
                f"• MAC address vendor lookup failed\n\n"
                f"This is NORMAL for security-conscious devices.\n"
                f"This message will only show once per scan."
            ))
    
    device_key = f"{mac}_{network}"
    if device_key in seen:
        return
    seen.add(device_key)

    def ui_insert():
        counts["devices"] += 1
        counts["active"] += 1
        insert_row((mac, vendor, ip, network))
        _update_status()
    app.after(0, ui_insert)

def multi_network_scan(networks):
    """Scan multiple networks"""
    for network in networks:
        if stop_event and stop_event.is_set():
            break
        
        app.after(0, lambda n=network: status_label.configure(text=f"Scanning: {n}"))
        
        # Modified callback to include network info
        def network_callback(mac, vendor, ip):
            scan_callback(mac, vendor, ip, network)
        
        # Run scan for this network
        try:
            ns.run_scan(network_callback, stop_event, target_network=network)
        except Exception as e:
            print(f"Error scanning {network}: {e}")

def start_scan():
    # Get network ranges to scan
    networks = get_network_ranges()
    if not networks:
        messagebox.showwarning("No Networks", "No networks selected for scanning!")
        return
    
    global current_networks, protected_popup_shown
    current_networks = networks
    protected_popup_shown = False  # Reset popup flag for new scan
    
    _spinner_on()
    global stop_event, scan_thread
    if scan_thread and scan_thread.is_alive():
        return
    # reset table + counters
    clear_rows()
    seen.clear()
    counts["devices"] = counts["active"] = 0
    _update_status()

    btn_start.configure(state="disabled")
    btn_stop.configure(state="normal")

    stop_event = threading.Event()
    scan_thread = threading.Thread(
        target=multi_network_scan,
        args=(networks,),
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

app.mainloop()

