# HomeNetSafe Database Module
# Handles all SQLite database operations for device management and history tracking

import sqlite3
import json
import os
from datetime import datetime

# SQLite database file name
DB_FILE = 'homenetsafe.db'

def init_db():
    """
    Initialize SQLite database with required tables.
    
    Creates two tables:
    1. devices - Main device information (IP, MAC, name, status, etc.)
    2. device_history - Event tracking for devices (connect/disconnect/changes)
    """
    conn = sqlite3.connect(DB_FILE)
    
    # Main devices table with all device information
    conn.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Unique device ID
            ip TEXT UNIQUE,                        -- IP address (unique constraint)
            mac TEXT,                              -- MAC address
            name TEXT,                             -- Device name/hostname
            vendor TEXT,                           -- Manufacturer (from MAC lookup)
            first_seen TEXT,                       -- When device was first discovered
            last_seen TEXT,                        -- Last time device was seen
            status TEXT DEFAULT 'unknown',         -- online/offline/unknown
            device_type TEXT DEFAULT 'unknown',    -- computer/phone/printer/etc
            manual BOOLEAN DEFAULT 0,              -- 1 if manually added, 0 if discovered
            created_at TEXT DEFAULT CURRENT_TIMESTAMP  -- When record was created
        )
    ''')
    
    # Device history table for tracking events and changes
    conn.execute('''
        CREATE TABLE IF NOT EXISTS device_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Unique event ID
            device_id INTEGER,                     -- Reference to devices.id
            event_type TEXT,                       -- Type of event (connect/disconnect/etc)
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,  -- When event occurred
            details TEXT,                          -- Additional event details
            FOREIGN KEY (device_id) REFERENCES devices (id)  -- Link to devices table
        )
    ''')
    
    conn.commit()
    conn.close()

def migrate_json_data():
    """
    Migrate existing manual_devices.json data to SQLite database.
    
    This function:
    1. Reads the old JSON file if it exists
    2. Inserts all devices into SQLite database
    3. Backs up the JSON file as .backup
    4. Only runs once (JSON file is renamed after migration)
    """
    json_file = 'manual_devices.json'
    if os.path.exists(json_file):
        try:
            # Read existing JSON data
            with open(json_file, 'r') as f:
                devices = json.load(f)
            
            # Insert each device into SQLite database
            conn = sqlite3.connect(DB_FILE)
            for device in devices:
                conn.execute('''
                    INSERT OR REPLACE INTO devices 
                    (ip, mac, name, vendor, first_seen, last_seen, manual)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (
                    device.get('ip', ''),
                    device.get('mac', ''),
                    device.get('name', ''),
                    device.get('vendor', 'Manual'),
                    device.get('first_seen', ''),
                    device.get('last_seen', '')
                ))
            conn.commit()
            conn.close()
            
            # Backup original JSON file and remove it
            os.rename(json_file, f"{json_file}.backup")
            print(f"Migrated {len(devices)} devices from JSON to SQLite")
        except Exception as e:
            print(f"Migration failed: {e}")

def get_manual_devices():
    """
    Retrieve all manually added devices from database.
    
    Returns:
        list: List of device dictionaries with all device properties
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    cursor = conn.execute('SELECT * FROM devices WHERE manual = 1 ORDER BY name')
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

def add_manual_device(ip, mac, name, vendor='Manual'):
    """
    Add a new manual device to the database.
    
    Args:
        ip (str): Device IP address
        mac (str): Device MAC address
        name (str): Device name/hostname
        vendor (str): Device manufacturer
        
    Returns:
        bool: True if device added successfully, False if IP already exists
    """
    conn = sqlite3.connect(DB_FILE)
    now = datetime.now().isoformat()
    try:
        conn.execute('''
            INSERT INTO devices (ip, mac, name, vendor, first_seen, last_seen, manual)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (ip, mac, name, vendor, now, now))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # IP address already exists in database (UNIQUE constraint violation)
        return False
    finally:
        conn.close()

def remove_manual_device(device_id):
    """
    Remove a manual device from database by its ID.
    
    Args:
        device_id (int): Database ID of device to remove
        
    Returns:
        bool: True if device was found and removed, False if not found
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute('DELETE FROM devices WHERE id = ? AND manual = 1', (device_id,))
    success = cursor.rowcount > 0  # True if any rows were deleted
    conn.commit()
    conn.close()
    return success

def get_device_count():
    """
    Get total number of devices in database.
    
    Returns:
        int: Total device count (manual + discovered)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute('SELECT COUNT(*) FROM devices')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_device_stats():
    """
    Get device statistics grouped by status.
    
    Returns:
        dict: {
            'total': total device count,
            'online': number of online devices,
            'offline': number of offline devices,
            'unknown': number of devices with unknown status
        }
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    
    # Count devices grouped by their status
    cursor = conn.execute('''
        SELECT status, COUNT(*) as count 
        FROM devices 
        GROUP BY status
    ''')
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    
    # Get total device count
    cursor = conn.execute('SELECT COUNT(*) as total FROM devices')
    total = cursor.fetchone()['total']
    
    conn.close()
    return {
        'total': total,
        'online': status_counts.get('online', 0),
        'offline': status_counts.get('offline', 0),
        'unknown': status_counts.get('unknown', 0)
    }

def get_device_history(device_id, limit=10):
    """
    Get event history for a specific device.
    
    Args:
        device_id (int): Database ID of device
        limit (int): Maximum number of history entries to return
        
    Returns:
        list: List of history events, newest first
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute('''
        SELECT * FROM device_history 
        WHERE device_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (device_id, limit))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history

def add_device_event(device_id, event_type, details=None):
    """
    Add a new event to device history.
    
    Args:
        device_id (int): Database ID of device
        event_type (str): Type of event (e.g., 'connected', 'disconnected', 'status_change')
        details (str, optional): Additional event details
    """
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        INSERT INTO device_history (device_id, event_type, details)
        VALUES (?, ?, ?)
    ''', (device_id, event_type, details))
    conn.commit()
    conn.close()

def get_device_type_icon(vendor, name):
    """
    Determine appropriate emoji icon for device based on vendor and name.
    
    Args:
        vendor (str): Device manufacturer/vendor name
        name (str): Device name or hostname
        
    Returns:
        str: Unicode emoji representing the device type
    """
    vendor_lower = (vendor or '').lower()
    name_lower = (name or '').lower()
    
    # Mobile devices
    if 'apple' in vendor_lower or 'iphone' in name_lower or 'ipad' in name_lower:
        return '📱'  # Apple devices
    elif 'samsung' in vendor_lower or 'android' in name_lower:
        return '📱'  # Android devices
    
    # Gaming devices
    elif 'nintendo' in vendor_lower:
        return '🎮'  # Nintendo gaming consoles
    
    # Single-board computers
    elif 'raspberry' in vendor_lower:
        return '🥧'  # Raspberry Pi
    
    # Smart speakers/IoT
    elif 'amazon' in vendor_lower or 'echo' in name_lower or 'alexa' in name_lower:
        return '🔊'  # Amazon Echo/Alexa devices
    
    # Printers
    elif 'hp' in vendor_lower or 'canon' in vendor_lower or 'epson' in vendor_lower or 'printer' in name_lower:
        return '🖨️'  # Printers
    
    # Network equipment
    elif 'router' in name_lower or 'netgear' in vendor_lower or 'linksys' in vendor_lower:
        return '📡'  # Routers and network equipment
    
    # Servers
    elif 'proxmox' in vendor_lower or 'server' in name_lower:
        return '🖥️'  # Servers and virtualization hosts
    
    # Smart home devices
    elif 'tuya' in vendor_lower or 'smart' in name_lower:
        return '🏠'  # Smart home/IoT devices
    
    # Default for unknown devices
    else:
        return '💻'  # Generic computer icon