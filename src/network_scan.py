import get_local_ip_address as host_ip
import scapy.all as scapy
from ipaddress import IPv4Interface
import socket, time

# Vendor lookup (optional: pip install manuf)
try:
    from manuf import manuf
    _parser = manuf.MacParser()
    def _vendor(mac):
        return _parser.get_manuf(mac) or _parser.get_manuf_long(mac) or "unknown"
except Exception:
    def _vendor(mac):
        return "unknown"

def run_scan(callback=None, stop_event=None, interval=30):
    """Continuously scan until stop_event is set."""
    try:
        count = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                break

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
                if stop_event is not None and stop_event.is_set():
                    break
                mac, ip = rcv.hwsrc, rcv.psrc
                if (mac, ip) in seen:
                    continue
                seen.add((mac, ip))
                vendor = _vendor(mac)
                if callback:
                    callback(mac, vendor, ip)
                else:
                    print(mac, vendor, ip)

            count += 1

            # Sleep in short chunks so we can stop promptly
            slept = 0
            while slept < interval:
                if stop_event is not None and stop_event.is_set():
                    break
                time.sleep(0.2)
                slept += 0.2
            if stop_event is not None and stop_event.is_set():
                break

    except KeyboardInterrupt:
        print(f"Program terminated, scan was ran: {count} times")

if __name__ == "__main__":
    run_scan()
