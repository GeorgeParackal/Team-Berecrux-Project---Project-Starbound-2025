# HomeNetSafe - Main Flask Application
# Handles network monitoring, device management, and web interface

from website import create_app
import subprocess
import sys
import os
import re
import json
import time
from flask import jsonify, request
# Import all database functions for device and history management
from database import init_db, migrate_json_data, get_manual_devices, add_manual_device, remove_manual_device, get_device_count, get_device_stats, get_device_history, add_device_event

def get_local_ip():
    """
    Get the local IP address of the active network interface.
    
    Returns:
        str: Local IP address or 'Unknown' if not found
    """
    try:
        import socket
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return 'Unknown'

def get_network_interface_info():
    """
    Detects current network interface type (WiFi vs Ethernet) and security info.
    Uses ipconfig to find active interface, then checks if it's WiFi or Ethernet.
    
    Returns:
        dict: {
            'type': 'wifi' or 'ethernet',
            'security': WiFi security type or 'Not using WiFi',
            'is_insecure': boolean indicating if connection is insecure,
            'local_ip': local IP address
        }
    """
    local_ip = get_local_ip()
    
    try:
        # Get active network interfaces with IP addresses
        ipconfig_result = subprocess.run(['ipconfig'], 
                                       capture_output=True, text=True, timeout=10)
        
        if ipconfig_result.returncode == 0:
            lines = ipconfig_result.stdout.split('\n')
            current_adapter = None
            has_ip = False
            
            for line in lines:
                line = line.strip()
                
                # Look for adapter names
                if 'adapter' in line.lower() and ':' in line:
                    # Save previous adapter if it had an IP (was active)
                    if current_adapter and has_ip:
                        # Check if this active adapter is WiFi
                        if any(wifi_keyword in current_adapter.lower() for wifi_keyword in 
                               ['wireless', 'wi-fi', 'wifi', 'wlan', '802.11']):
                            wifi_info = get_wifi_security_info()
                            wifi_info['local_ip'] = local_ip
                            return wifi_info
                        elif any(eth_keyword in current_adapter.lower() for eth_keyword in 
                                ['ethernet', 'local area connection', 'eth']):
                            return {'type': 'ethernet', 'security': 'Not using WiFi', 'is_insecure': False, 'local_ip': local_ip}
                    
                    # Start tracking new adapter
                    current_adapter = line
                    has_ip = False
                
                # Check if current adapter has an IP address (is active)
                elif 'IPv4 Address' in line or 'IP Address' in line:
                    if '192.168.' in line or '10.' in line or '172.' in line or not '169.254.' in line:
                        has_ip = True
            
            # Check the last adapter
            if current_adapter and has_ip:
                if any(wifi_keyword in current_adapter.lower() for wifi_keyword in 
                       ['wireless', 'wi-fi', 'wifi', 'wlan', '802.11']):
                    wifi_info = get_wifi_security_info()
                    wifi_info['local_ip'] = local_ip
                    return wifi_info
                elif any(eth_keyword in current_adapter.lower() for eth_keyword in 
                        ['ethernet', 'local area connection', 'eth']):
                    return {'type': 'ethernet', 'security': 'Not using WiFi', 'is_insecure': False, 'local_ip': local_ip}
        
        # Fallback: Default to Ethernet
        return {'type': 'ethernet', 'security': 'Not using WiFi', 'is_insecure': False, 'local_ip': local_ip}
        
    except Exception:
        # Fallback to Ethernet on any error
        return {'type': 'ethernet', 'security': 'Not using WiFi', 'is_insecure': False, 'local_ip': local_ip}

def get_wifi_security_info():
    """
    Get WiFi security information when WiFi is detected as active interface.
    
    Returns:
        dict: WiFi connection details with security info
    """
    try:
        wifi_result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                                   capture_output=True, text=True, timeout=10)
        
        if wifi_result.returncode == 0:
            lines = wifi_result.stdout.split('\n')
            security = 'Unknown'
            
            for line in lines:
                line = line.strip().lower()
                if 'authentication' in line:
                    if 'wpa3' in line: security = 'WPA3'
                    elif 'wpa2' in line: security = 'WPA2'
                    elif 'wpa' in line: security = 'WPA'
                    elif 'wep' in line: security = 'WEP'
                    elif 'open' in line: security = 'Open'
            
            is_insecure = security in ['WEP', 'Open', 'Unknown']
            return {
                'type': 'wifi',
                'security': security,
                'is_insecure': is_insecure
            }
    except Exception:
        pass
    
    # Fallback if WiFi info can't be retrieved
    return {
        'type': 'wifi',
        'security': 'Unknown',
        'is_insecure': True
    }

def setup_database():
    """
    Initialize SQLite database and migrate any existing JSON data.
    
    This function:
    1. Creates database tables if they don't exist
    2. Migrates data from manual_devices.json to SQLite
    3. Backs up the JSON file after successful migration
    """
    init_db()  # Create tables if they don't exist
    migrate_json_data()  # Move JSON data to SQLite

def main():
    """
    Main Flask application entry point.
    Sets up database, creates Flask app, and defines all API routes.
    """
    # Initialize database and migrate any existing JSON data on startup
    setup_database()
    
    # Create Flask app instance from website module
    app = create_app()
    
    # === MONITORING & HEALTH ENDPOINTS ===
    
    @app.route('/health')
    def health_check():
        """
        Health check endpoint for monitoring system status.
        Returns server health, timestamp, and total device count.
        """
        return jsonify({
            'status': 'healthy', 
            'timestamp': time.time(),
            'device_count': get_device_count()
        })
    
    @app.route('/device-stats')
    def device_stats():
        """
        Get device statistics (total, online, offline, unknown counts).
        Used by frontend to display device summary in header.
        """
        return jsonify(get_device_stats())
    
    @app.route('/device-history/<int:device_id>')
    def device_history(device_id):
        """
        Get history/timeline for a specific device.
        Returns list of events (connect/disconnect/status changes).
        """
        return jsonify(get_device_history(device_id))
    
    # === NETWORK INTERFACE DETECTION ===
    
    @app.route('/network-interface')
    def network_interface():
        """
        Detect current network interface (WiFi vs Ethernet) and security info.
        Used by frontend to show network type indicator in header.
        """
        result = get_network_interface_info()
        return jsonify(result)
    
    # === DEVICE MANAGEMENT ENDPOINTS ===
    
    @app.route('/manual-devices', methods=['GET'])
    def get_devices():
        """
        Get all manually added devices from database.
        Returns list of devices with all their properties.
        """
        return jsonify(get_manual_devices())
    
    @app.route('/manual-devices', methods=['POST'])
    def add_device():
        """
        Add a new manual device to the database.
        Expects JSON with: ip, mac, name, vendor fields.
        Returns success/error status.
        """
        data = request.json
        success = add_manual_device(
            data.get('ip', ''),
            data.get('mac', ''),
            data.get('name', ''),
            data.get('vendor', 'Manual')
        )
        if success:
            return jsonify({'ok': True})
        else:
            # Return 400 if device already exists (duplicate IP)
            return jsonify({'ok': False, 'error': 'Device already exists'}), 400
    
    @app.route('/manual-devices/<int:device_id>', methods=['DELETE'])
    def remove_device(device_id):
        """
        Remove a manual device by its database ID.
        Returns success/error status.
        """
        success = remove_manual_device(device_id)
        if success:
            return jsonify({'ok': True})
        else:
            # Return 404 if device not found
            return jsonify({'ok': False, 'error': 'Device not found'}), 404
    
    # === NETWORK SCANNING ENDPOINT ===
    
    @app.route('/run-script')
    def run_script():
        """
        Execute the Device Discovery Python script for network scanning.
        Runs the script as subprocess and returns stdout/stderr.
        Used by 'Scan Network' button in frontend.
        """
        script_path = os.path.join(os.path.dirname(__file__), "Device Discovery.py")
        if not os.path.exists(script_path):
            return jsonify({"ok": False, "stdout": "", "stderr": "Device discovery script not found"}), 500
        
        try:
            # Run the discovery script with 30-second timeout
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            return jsonify({
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            })
        except subprocess.TimeoutExpired:
            return jsonify({"ok": False, "stdout": "", "stderr": "Script timeout"}), 500
        except Exception as e:
            return jsonify({"ok": False, "stdout": "", "stderr": str(e)}), 500
    
    # === START FLASK SERVER ===
    
    # Use production settings if FLASK_ENV=production, otherwise development
    if os.environ.get('FLASK_ENV') == 'production':
        # Production: no debug, bind to all interfaces
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        # Development: debug enabled, suppress SSL errors
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(debug=True, host='0.0.0.0', port=5000)

# Entry point - run the Flask application
if __name__ == '__main__':
    main()