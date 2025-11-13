import json
import os
import time
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

class DeviceAlerts:
    def __init__(self, known_devices_file="known_devices.json"):
        self.known_devices_file = known_devices_file
        self.known_devices = self.load_known_devices()
        
    def load_known_devices(self):
        """Load known devices from file"""
        if os.path.exists(self.known_devices_file):
            with open(self.known_devices_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_known_devices(self):
        """Save known devices to file"""
        with open(self.known_devices_file, 'w') as f:
            json.dump(self.known_devices, f, indent=2)
    
    def check_new_device(self, mac, vendor, ip):
        """Check if device is new and trigger alert if needed"""
        if mac not in self.known_devices:
            self.alert_new_device(mac, vendor, ip)
            self.add_device(mac, vendor, ip)
            return True
        return False
    
    def add_device(self, mac, vendor, ip):
        """Add device to known devices"""
        self.known_devices[mac] = {
            "vendor": vendor,
            "ip": ip,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        self.save_known_devices()
    
    def alert_new_device(self, mac, vendor, ip):
        """Show alert for new device"""
        message = f"NEW DEVICE DETECTED!\n\nMAC: {mac}\nVendor: {vendor}\nIP: {ip}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Console alert
        print(f"[ALERT] {message}")
        
        # GUI alert (if tkinter available)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("New Device Alert", message)
            root.destroy()
        except:
            pass
    
    def update_device_seen(self, mac):
        """Update last seen time for existing device"""
        if mac in self.known_devices:
            self.known_devices[mac]["last_seen"] = datetime.now().isoformat()
            self.save_known_devices()

# Usage example
if __name__ == "__main__":
    alerts = DeviceAlerts()
    # Test alert
    alerts.check_new_device("00:11:22:33:44:55", "Test Vendor", "192.168.1.100")