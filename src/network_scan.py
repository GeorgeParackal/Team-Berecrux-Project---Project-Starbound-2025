import get_local_ip_address as host_ip
import scapy.all as scapy
from ipaddress import IPv4Interface
import socket
import time



try:
    count = 0
    while True:
        hostname=socket.gethostname()
        print(hostname)
        host_ip_address = host_ip.get_local_ip_address()
        network=str(IPv4Interface(host_ip_address+"/24").network)
        scapy.arping(network)
        count += 1
        time.sleep(30)
except KeyboardInterrupt:
    print(f"Program terminated, scan was ran: {count} times")
