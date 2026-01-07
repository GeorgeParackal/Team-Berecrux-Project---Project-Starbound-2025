import threading, queue, tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import importlib, inspect, network_scan
import time, json, os, hashlib, csv

# Force-reload scanner code
importlib.reload(network_scan)
run_scan = network_scan.run_scan

# =========================
# CONFIG
# =========================
APP_TITLE = "Multi-Network Scanner Pro v2.1"
BG_DARK = "#2C3E50"
CARD = "#34495E"
ACCENT = "#3498DB"
ACCENT_HOVER = "#2980B9"
TEXT = "#ECF0F1"
TEXT_MUTED = "#BDC3C7"
SUCCESS = "#27AE60"
DANGER = "#E74C3C"
WARNING = "#F39C12"

class MultiNetworkScanner:
    def __init__(self):
        self.q = queue.Queue()
        self.scan_thread = None
        self.stop_event = threading.Event()
        self.known_devices = {}
        self.scan_start_time = None
        self.protected_networks = self.load_protected_networks()
        self.current_networks = []
        
        self.setup_gui()
        self.show_disclaimer()
    
    def load_protected_networks(self):
        """Load password-protected networks from file"""
        if os.path.exists("protected_networks.json"):
            with open("protected_networks.json", 'r') as f:
                return json.load(f)
        return {}
    
    def save_protected_networks(self):
        """Save protected networks to file"""
        with open("protected_networks.json", 'w') as f:
            json.dump(self.protected_networks, f, indent=2)
    
    def show_disclaimer(self):
        """Show legal disclaimer"""
        disclaimer = """⚠️ LEGAL DISCLAIMER ⚠️

This network scanner should ONLY be used on:
• Networks you own
• Networks you have explicit permission to scan
• Your home/personal networks

UNAUTHORIZED NETWORK SCANNING IS ILLEGAL

By clicking 'I Agree', you confirm:
✓ You own or have permission to scan target networks
✓ You will not use this tool for malicious purposes
✓ You understand legal consequences of unauthorized scanning

For unknown/protected devices:
• Router manufacturers may not share device names for privacy
• Some devices intentionally hide their identity for security"""
        
        result = messagebox.askyesno("Legal Disclaimer", disclaimer)
        if not result:
            self.root.destroy()
            return
    
    def hash_password(self, password):
        """Hash password for storage"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def check_network_access(self, network_range):
        """Check if network requires password"""
        if network_range in self.protected_networks:
            password = simpledialog.askstring(
                "Protected Network", 
                f"Network {network_range} is password protected.\nEnter password:",
                show='*'
            )
            if not password:
                return False
            
            hashed = self.hash_password(password)
            if hashed != self.protected_networks[network_range]:
                messagebox.showerror("Access Denied", "Incorrect password!")
                return False
        return True
    
    def protect_network(self):
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
        
        self.protected_networks[network] = self.hash_password(password)
        self.save_protected_networks()
        messagebox.showinfo("Success", f"Network {network} is now protected!")
    
    def get_network_ranges(self):
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
            if self.check_network_access(network):
                networks.append(network)
            else:
                messagebox.showwarning("Access Denied", f"Cannot scan protected network: {network}")
        
        return networks
    
    def on_new_device(self, mac, vendor, ip, network=None):
        """Handle new device discovery"""
        # Privacy protection for unknown devices
        if vendor.lower() in ['unknown', '', 'n/a']:
            vendor = "🔒 Protected Identity"
        
        self.q.put((mac, vendor, ip, network or "Unknown"))
    
    def device_type_from_vendor(self, vendor):
        """Determine device type from vendor"""
        v = vendor.lower()
        if "router" in v or "gateway" in v or "ubiquiti" in v:
            return "🌐 Router"
        elif "apple" in v:
            return "🍎 Apple"
        elif "samsung" in v:
            return "📱 Samsung"
        elif "protected" in v:
            return "🔒 Protected"
        elif "raspberry" in v:
            return "🧪 Raspberry Pi"
        else:
            return "💻 Device"
    
    def poll_queue(self):
        """Process device queue"""
        try:
            while True:
                mac, vendor, ip, network = self.q.get_nowait()
                
                device_type = self.device_type_from_vendor(vendor)
                device_key = f"{mac}_{network}"
                
                if device_key in self.known_devices:
                    item_id = self.known_devices[device_key]
                    current_values = self.tree.item(item_id, "values")
                    if current_values != (device_type, mac, vendor, ip, network, "Active"):
                        self.tree.item(item_id, values=(device_type, mac, vendor, ip, network, "Active"))
                else:
                    item_id = self.tree.insert("", "end", values=(device_type, mac, vendor, ip, network, "Active"))
                    self.known_devices[device_key] = item_id
        
        except queue.Empty:
            pass
        
        self.root.after(100, self.poll_queue)
    
    def start_scan(self):
        """Start multi-network scan"""
        networks = self.get_network_ranges()
        if not networks:
            messagebox.showwarning("No Networks", "No networks selected for scanning!")
            return
        
        self.current_networks = networks
        
        # Clear previous data
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.known_devices.clear()
        self.scan_start_time = time.time()
        
        # Create new stop event
        self.stop_event = threading.Event()
        
        # Start scan thread for multiple networks
        self.scan_thread = threading.Thread(
            target=self.multi_network_scan,
            args=(networks,),
            daemon=True
        )
        self.scan_thread.start()
        
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.update_progress()
    
    def multi_network_scan(self, networks):
        """Scan multiple networks"""
        for network in networks:
            if self.stop_event.is_set():
                break
            
            # Modified callback to include network info
            def network_callback(mac, vendor, ip):
                self.on_new_device(mac, vendor, ip, network)
            
            # Run scan for this network
            try:
                run_scan(network_callback, self.stop_event, target_network=network)
            except Exception as e:
                print(f"Error scanning {network}: {e}")
    
    def stop_scan(self):
        """Stop scanning"""
        if self.stop_event:
            self.stop_event.set()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.update_progress()
    
    def export_csv(self):
        """Export device list to CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Device Type", "MAC Address", "Vendor", "IP Address", "Network", "Status"])
                
                for item in self.tree.get_children():
                    values = self.tree.item(item, "values")
                    writer.writerow(values)
            
            messagebox.showinfo("Export Complete", f"Device list exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")
    
    def update_progress(self):
        """Update progress bar"""
        if self.scan_thread and self.scan_thread.is_alive():
            self.progress_bar['mode'] = 'indeterminate'
            self.progress_bar.start(10)
            elapsed = time.time() - self.scan_start_time if self.scan_start_time else 0
            self.status_var.set(f"Multi-network scanning... ({elapsed:.0f}s)")
        else:
            self.progress_bar.stop()
            self.progress_bar['mode'] = 'determinate'
            self.progress_bar['value'] = 0
            self.status_var.set("Scan stopped")
    
    def setup_gui(self):
        """Setup the GUI"""
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1000x700")
        self.root.configure(bg=BG_DARK)
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background=BG_DARK, foreground=TEXT)
        style.configure('Header.TFrame', background=CARD)
        style.configure('Treeview', background=TEXT, foreground=BG_DARK, fieldbackground=TEXT)
        style.configure('Treeview.Heading', background=ACCENT, foreground='white', font=('Arial', 10, 'bold'))
        style.map('Treeview', background=[('selected', ACCENT)])
        
        # Header
        header_frame = ttk.Frame(self.root, style='Header.TFrame')
        header_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        title_label = ttk.Label(header_frame, text="🔍 Multi-Network Scanner Pro", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Device list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        columns = ("Type", "MAC Address", "Vendor", "IP Address", "Network", "Status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.tree.heading('Type', text='Device Type', anchor='center')
        self.tree.column('Type', width=120, anchor='center')
        self.tree.heading('MAC Address', text='MAC Address', anchor='center')
        self.tree.column('MAC Address', width=140, anchor='center')
        self.tree.heading('Vendor', text='Vendor/Manufacturer', anchor='center')
        self.tree.column('Vendor', width=180, anchor='center')
        self.tree.heading('IP Address', text='IP Address', anchor='center')
        self.tree.column('IP Address', width=120, anchor='center')
        self.tree.heading('Network', text='Network Range', anchor='center')
        self.tree.column('Network', width=140, anchor='center')
        self.tree.heading('Status', text='Status', anchor='center')
        self.tree.column('Status', width=80, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Multi-Network Controls", padding=10)
        control_frame.pack(fill='x', pady=(0, 10))
        
        # Progress bar
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(fill='x', pady=(0, 10))
        
        progress_label = ttk.Label(progress_frame, text="Scan Progress:")
        progress_label.pack(anchor='w')
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(fill='x', pady=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill='x')
        
        self.start_btn = ttk.Button(button_frame, text="🚀 Start Multi-Network Scan", command=self.start_scan)
        self.start_btn.pack(side='left', padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="⏹️ Stop Scan", command=self.stop_scan, state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 10))
        
        protect_btn = ttk.Button(button_frame, text="🔒 Protect Network", command=self.protect_network)
        protect_btn.pack(side='left', padx=(0, 10))
        
        export_btn = ttk.Button(button_frame, text="📄 Export CSV", command=self.export_csv)
        export_btn.pack(side='left', padx=(0, 10))
        
        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill='x', side='bottom', padx=10, pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Ready for multi-network scan")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, font=('Arial', 9))
        self.status_label.pack(anchor='w')
        
        self.device_count_var = tk.StringVar(value="Devices found: 0")
        self.device_count_label = ttk.Label(status_frame, textvariable=self.device_count_var, font=('Arial', 9))
        self.device_count_label.pack(anchor='e')
    
    def update_device_count(self):
        """Update device count"""
        self.device_count_var.set(f"Devices found: {len(self.known_devices)}")
        if self.scan_thread and self.scan_thread.is_alive():
            self.update_progress()
        self.root.after(1000, self.update_device_count)
    
    def run(self):
        """Start the application"""
        self.update_device_count()
        self.poll_queue()
        self.root.mainloop()

if __name__ == "__main__":
    app = MultiNetworkScanner()
    app.run()_col(idx):
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
