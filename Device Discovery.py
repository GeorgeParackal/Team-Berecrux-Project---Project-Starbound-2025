from datetime import datetime
from scapy.all import srp, Ether, ARP, conf
import time

def arp_scan(interface, ips, timeout=2, retries=3):
    print("[->] Scanning")
    start = datetime.now()
    conf.verb = 0
    #silent mode on Scapy, keeps output clean

    found = {}
    #empty dict to store found devices, tying IP to MAC


#srp returns ans, unans - answered packts and unanswered packets, for now we will ignore the second value with an underscore
    for i in range(retries):
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ips),timeout=timeout, iface=interface, inter=0.1)
        for _, recivedPack in ans:
            found[recivedPack.psrc] = recivedPack.hwsrc
        time.sleep(0.2)

    print("\n[->] IP - MAC Address")
    for ip, mac in sorted(found.items()):
        print(f"{ip} - {mac}")

    print("\n[->] Scan Complete. Duration:", datetime.now() - start)

import socket
import ipaddress

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "192.168.1.100"  # fallback

def auto_detect_network():
    local_ip = get_local_ip()
    try:
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        return str(network)
    except:
        return "192.168.1.0/24"

# Auto-detect network and interface
network_cidr = auto_detect_network()
# Common Windows interface names: "Wi-Fi", "Ethernet", "Local Area Connection"
# Run 'ipconfig' to see your interface names
interface = "Ethernet"  # Try "Ethernet" if "Wi-Fi" doesn't work

print(f"Scanning network: {network_cidr} on interface: {interface}")
arp_scan(interface, network_cidr, timeout=3, retries=4)

#WILL ADD list of manufac, just refence a JSON instead of putting it in here. 

# ---note---
# code will take a while to run, it's making sure mulitple passes are done and waits between each pass to allow
# for unanswered devices and powered off devices to answer

#AGAIN CODE only returns an IP if the device is powered on and is able to respond to ARP scan