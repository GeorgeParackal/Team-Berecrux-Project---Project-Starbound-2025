import scapy.all as scapy
from ipaddress import IPv4Interface
import time
import socket
import get_local_ip_address as host_ip

def run_scan(callback=None, stop_event=None, cycle_callback=None, interval_sec=30):
    """Run the network scan, optionally sending results to a callback."""
    count = 0
    while True:
        if stop_event and stop_event.is_set():
            break

        try:
            # Compute /24 from current IP each cycle (handles Wi-Fi changes)
            host_ip_address = host_ip.get_local_ip_address()
            network = str(IPv4Interface(host_ip_address + "/24").network)

            # IMPORTANT: bound the scan time so the loop keeps advancing
            # timeout caps how long to wait for replies; retry keeps it quick
            ans, _ = scapy.arping(network, timeout=3, retry=0, verbose=False)

            for _, rcv in ans:
                mac = rcv.hwsrc
                ip = rcv.psrc
                vendor = "unknown"
                if callback:
                    callback(mac, vendor, ip)
                else:
                    print(mac, vendor, ip)

            # advance cycle count and notify UI
            count += 1
            if cycle_callback:
                cycle_callback(count)
            else:
                print(f"Scan cycles: {count}")

        except Exception as e:
            # Don’t kill the thread on intermittent errors; still tick the cycle
            count += 1
            if cycle_callback:
                cycle_callback(count)
            print(f"[run_scan] cycle {count} error: {e}", flush=True)

        # Sleep in short chunks so stop_event is responsive
        slept = 0.0
        while slept < interval_sec and not (stop_event and stop_event.is_set()):
            time.sleep(0.2)
            slept += 0.2
