import get_local_ip_address as host_ip
import scapy.all as scapy
from ipaddress import IPv4Interface
import socket
import time

# Vendor lookup (requires: pip install manuf)
try:
    from manuf import manuf
    _parser = manuf.MacParser()
    def _vendor(mac):
        return _parser.get_manuf(mac) or _parser.get_manuf_long(mac) or "unknown"
except Exception:
    def _vendor(mac):
        return "unknown"

def run_scan(callback=None):
    """Continuously scans the local network and sends results to callback."""
    try:
        count = 0
        while True:
            hostname = socket.gethostname()
            host_ip_address = host_ip.get_local_ip_address()
            network = str(IPv4Interface(host_ip_address + '/24').network)

            try:
                ans, _ = scapy.arping(network, timeout=2, retry=1, verbose=False)
            except Exception as e:
                if callback:
                    callback("error", "scan_failed", str(e))
                time.sleep(5)
                continue

            seen = set()
            for _, rcv in ans:
                mac = rcv.hwsrc
                ip = rcv.psrc
                if (mac, ip) in seen:
                    continue
                seen.add((mac, ip))
                vendor = _vendor(mac)
                if callback:
                    callback(mac, vendor, ip)
                else:
                    print(mac, vendor, ip)

            count += 1
            time.sleep(30)

    except KeyboardInterrupt:
        print(f"Program terminated, scan was ran: {count} times")

if __name__ == "__main__":
    run_scan()
