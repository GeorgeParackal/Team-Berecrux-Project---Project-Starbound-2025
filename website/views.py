import json

from flask import Blueprint, render_template, request, flash, jsonify

try:
    from .scan_device import _get_local_ip, build_network_device_list, Network_Device
except ImportError:
    # Fallback for missing dependencies
    def _get_local_ip():
        return "127.0.0.1"
    
    def build_network_device_list():
        return {}
    
    class Network_Device:
        def __init__(self, ip=None, mac=None, vendor=None, last_seen=None, first_seen=None):
            self.ip = ip
            self.mac = mac
            self.vendor = vendor
            self.last_seen = last_seen
            self.first_seen = first_seen

views = Blueprint('views', __name__)

@views.route('/', methods=['GET'])
def home():
    return render_template("home.html")

@views.route('/get_network_device_list', methods=['GET'])
def get_local_device_ip():
    device_registry = build_network_device_list()

    network_device_list = []

    for ip in device_registry:
        network_device_list.append(
            Network_Device(
                ip, 
                device_registry[ip]['mac'], 
                device_registry[ip]['vendor'],
                device_registry[ip]['last_seen'],
                device_registry[ip]['first_seen']
            )
        )


    return jsonify([x.__dict__ for x in network_device_list])

