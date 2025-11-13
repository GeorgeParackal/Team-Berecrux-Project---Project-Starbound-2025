import get_local_ip_address as host_ip
import scapy.all as scapy
from ipaddress import IPv4Interface
import socket
import time

def run_scan(callback=None):
    """Run the network scan, optionally sending results to a callback."""
    try:
        count = 0
        while True:
            hostname = socket.gethostname()
            host_ip_address = host_ip.get_local_ip_address()
            network = str(IPv4Interface(host_ip_address + '/24').network)
            ans, _ = scapy.arping(network, verbose=False)

            for _, rcv in ans:
                mac = rcv.hwsrc
                ip = rcv.psrc
                vendor = "unknown"
                if callback:
                    callback(mac, vendor, ip)
                else:
                    print(mac, vendor, ip)

            count += 1
            time.sleep(30)

    except KeyboardInterrupt:
        print(f"Program terminated, scan was ran: {count} times")

if __name__ == "__main__":
    # Run only if this file is executed directly
    run_scan()
