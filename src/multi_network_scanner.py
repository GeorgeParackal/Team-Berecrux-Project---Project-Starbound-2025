import threading, queue, tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import importlib, inspect, network_scan
import time
import json
import os
import hashlib

# Force-reload scanner code
importlib.reload(network_scan)
run_scan = network_scan.run_scan

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
        disclaimer = """
⚠️ LEGAL DISCLAIMER ⚠️

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
• Some devices intentionally hide their identity for security
        """
        
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
            messagebox.showinfo(
                "Privacy Notice", 
                f"Device {ip} identity is protected.\nRouter manufacturers may hide device names for privacy/security."
            )
        
        self.q.put((mac, vendor, ip, network or "Unknown"))
    
    def poll_queue(self):
        """Process device queue"""
        try:
            while True:
                mac, vendor, ip, network = self.q.get_nowait()
                
                # Determine device type
                if "router" in vendor.lower() or "gateway" in vendor.lower():
                    device_type = "🌐 Router"
                elif "apple" in vendor.lower():
                    device_type = "🍎 Apple"
                elif "samsung" in vendor.lower():
                    device_type = "📱 Samsung"
                elif "protected" in vendor.lower():
                    device_type = "🔒 Protected"
                else:
                    device_type = "💻 Device"
                
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
            
            self.status_label.config(text=f"Scanning network: {network}")
            
            # Modified callback to include network info
            def network_callback(mac, vendor, ip):
                self.on_new_device(mac, vendor, ip, network)
            
            # Run scan for this network (simplified - you'd need to modify network_scan.py)
            try:
                run_scan(network_callback, self.stop_event)
            except Exception as e:
                print(f"Error scanning {network}: {e}")
    
    def stop_scan(self):
        """Stop scanning"""
        if self.stop_event:
            self.stop_event.set()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.update_progress()
    
    def update_progress(self):
        """Update progress bar"""
        if self.scan_thread and self.scan_thread.is_alive():
            self.progress_bar['mode'] = 'indeterminate'
            self.progress_bar.start(10)
            elapsed = time.time() - self.scan_start_time if self.scan_start_time else 0
            self.status_label.config(text=f"Multi-network scanning... ({elapsed:.0f}s)", foreground="#2E8B57")
        else:
            self.progress_bar.stop()
            self.progress_bar['mode'] = 'determinate'
            self.progress_bar['value'] = 0
            self.status_label.config(text="Scan stopped", foreground="#DC143C")
    
    def setup_gui(self):
        """Setup the GUI"""
        self.root = tk.Tk()
        self.root.title("Multi-Network Scanner Pro v2.1")
        self.root.geometry("900x700")
        self.root.configure(bg="#2C3E50")
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#2C3E50', foreground='#ECF0F1')
        style.configure('Header.TFrame', background='#34495E')
        style.configure('Treeview', background='#ECF0F1', foreground='#2C3E50', fieldbackground='#ECF0F1')
        style.configure('Treeview.Heading', background='#3498DB', foreground='white', font=('Arial', 10, 'bold'))
        
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
        
        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill='x', side='bottom', padx=10, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Ready for multi-network scan", font=('Arial', 9))
        self.status_label.pack(anchor='w')
        
        self.device_count_label = ttk.Label(status_frame, text="Devices found: 0", font=('Arial', 9))
        self.device_count_label.pack(anchor='e')
    
    def update_device_count(self):
        """Update device count"""
        self.device_count_label.config(text=f"Devices found: {len(self.known_devices)}")
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
    app.run()