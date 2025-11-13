import socket
import threading
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor

class SecurityRiskScanner:
    def __init__(self):
        self.common_ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 993, 995, 1433, 3389, 5432, 5900]
        self.weak_passwords = ["admin", "password", "123456", "default", "guest", "root", ""]
        self.security_risks = []
    
    def scan_port(self, ip, port, timeout=1):
        """Scan single port on target IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def scan_open_ports(self, ip):
        """Scan for open ports on target"""
        open_ports = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self.scan_port, ip, port): port for port in self.common_ports}
            for future in futures:
                if future.result():
                    open_ports.append(futures[future])
        return open_ports
    
    def get_service_banner(self, ip, port):
        """Get service banner from open port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, port))
            sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            sock.close()
            return banner.strip()
        except:
            return ""
    
    def check_weak_services(self, ip, port):
        """Check for weak/default configurations"""
        risks = []
        
        # Check for common weak services
        if port == 23:  # Telnet
            risks.append(f"Telnet service on port {port} - Unencrypted protocol")
        elif port == 21:  # FTP
            risks.append(f"FTP service on port {port} - Check for anonymous access")
        elif port == 135 or port == 139:  # SMB
            risks.append(f"SMB service on port {port} - Check for null sessions")
        elif port == 5900:  # VNC
            risks.append(f"VNC service on port {port} - Check for weak authentication")
        
        # Get banner and check for outdated versions
        banner = self.get_service_banner(ip, port)
        if banner:
            if re.search(r'Server: Apache/2\.[0-2]', banner):
                risks.append(f"Outdated Apache version detected on port {port}")
            elif re.search(r'nginx/1\.[0-9]\.', banner):
                risks.append(f"Potentially outdated nginx on port {port}")
        
        return risks
    
    def scan_device_security(self, ip):
        """Perform comprehensive security scan on device"""
        print(f"Scanning {ip} for security risks...")
        device_risks = []
        
        # Scan for open ports
        open_ports = self.scan_open_ports(ip)
        if open_ports:
            device_risks.append(f"Open ports found: {', '.join(map(str, open_ports))}")
            
            # Check each open port for vulnerabilities
            for port in open_ports:
                port_risks = self.check_weak_services(ip, port)
                device_risks.extend(port_risks)
        
        # Check for ping response (device discovery)
        if self.ping_host(ip):
            device_risks.append("Device responds to ping - Consider disabling ICMP if not needed")
        
        return device_risks
    
    def ping_host(self, ip):
        """Check if host responds to ping"""
        try:
            result = subprocess.run(['ping', '-n', '1', '-w', '1000', ip], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def scan_network_security(self, device_list, callback=None):
        """Scan multiple devices for security risks"""
        all_risks = {}
        
        for mac, vendor, ip in device_list:
            risks = self.scan_device_security(ip)
            if risks:
                all_risks[ip] = {
                    'mac': mac,
                    'vendor': vendor,
                    'risks': risks
                }
                if callback:
                    callback(ip, mac, vendor, risks)
        
        return all_risks
    
    def generate_security_report(self, scan_results):
        """Generate security risk report"""
        report = "SECURITY RISK REPORT\n" + "="*50 + "\n\n"
        
        if not scan_results:
            report += "No security risks detected.\n"
            return report
        
        for ip, data in scan_results.items():
            report += f"Device: {ip} ({data['vendor']})\n"
            report += f"MAC: {data['mac']}\n"
            report += "Risks:\n"
            for risk in data['risks']:
                report += f"  - {risk}\n"
            report += "\n"
        
        return report

# Usage example
if __name__ == "__main__":
    scanner = SecurityRiskScanner()
    # Test scan
    risks = scanner.scan_device_security("192.168.1.1")
    print("Security risks found:", risks)