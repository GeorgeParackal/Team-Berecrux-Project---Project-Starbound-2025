import socket

def get_local_ip_address():
    # Option 1: via socket (more reliable cross-platform)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()
    return local_ip

if __name__=="main":
    get_local_ip_address()

