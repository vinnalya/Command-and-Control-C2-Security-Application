from db import get_db_connection
import logging
import time


def add_device(user_id, os_name, os_version, installed_apps, online_timestamp, geolocation):
    conn = get_db_connection()
    cursor = conn.cursor()

    installed_apps_str = ', '.join(installed_apps)

    cursor.execute(
        'INSERT INTO devices (user_id, os_name, os_version, installed_apps, online_timestamp, geolocation, watchlist) VALUES (?, ?, ?, ?, ?, ?, 1)',
        (user_id, os_name, os_version, installed_apps_str, online_timestamp, geolocation)
    )
    device_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return device_id


def verify_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, role FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    return user if user else None







def get_all_devices(user_id=None):
    conn = get_db_connection()
    
    if user_id:
        devices = conn.execute('SELECT * FROM devices WHERE user_id = ?', (user_id,)).fetchall()
    else:
        devices = conn.execute('SELECT * FROM devices').fetchall()
    
    conn.close()
    return devices





def update_offline_timestamp(device_id, offline_timestamp):
    conn = get_db_connection()
    conn.execute('''
        UPDATE devices
        SET offline_timestamp = ?
        WHERE id = ?
    ''', (offline_timestamp, device_id))
    conn.commit()
    conn.close()
    logging.info(f"Updated offline timestamp for device {device_id}: {offline_timestamp}")



def update_online_timestamp(device_id):
    conn = get_db_connection()
    online_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    conn.execute('''
        UPDATE devices
        SET online_timestamp = ?, offline_timestamp = NULL
        WHERE id = ?
    ''', (online_time, device_id))
    conn.commit()
    conn.close()
    logging.info(f"Updated online timestamp for device {device_id}: {online_time}")



def get_device_by_id(device_id):
    conn = get_db_connection()
    device = conn.execute('SELECT * FROM devices WHERE id = ?', (device_id,)).fetchone()
    conn.close()
    return device if device else None




def add_device_to_watchlist(device_id):
    conn = get_db_connection()
    conn.execute('UPDATE devices SET watchlist = 1 WHERE id = ?', (device_id,))
    conn.commit()
    conn.close()
    logging.info(f"Device {device_id} added to watchlist.")




def remove_device_from_watchlist(device_id):
    conn = get_db_connection()
    conn.execute('UPDATE devices SET watchlist = 0 WHERE id = ?', (device_id,))
    conn.commit()
    conn.close()
    logging.info(f"Device {device_id} removed from watchlist.")




def update_allow_info_view(device_id, allow_view):
    conn = get_db_connection()
    conn.execute('UPDATE devices SET allow_info_view = ? WHERE id = ?', (allow_view, device_id))
    conn.commit()
    conn.close()



def update_allow_interaction_history_view(device_id, allow_view):
    conn = get_db_connection()
    conn.execute('UPDATE devices SET allow_interaction_history_view = ? WHERE id = ?', (allow_view, device_id))
    conn.commit()
    conn.close()


def log_interaction(device_id, interaction_type, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    cursor.execute(
        'INSERT INTO interaction_history (device_id, interaction_type, details, timestamp) VALUES (?, ?, ?, ?)',
        (device_id, interaction_type, details, timestamp)
    )
    conn.commit()
    conn.close()
    logging.info(f"Interaction logged: {interaction_type} for device {device_id}")


def get_interaction_history(device_id):
    conn = get_db_connection()
    history = conn.execute('SELECT * FROM interaction_history WHERE device_id = ?', (device_id,)).fetchall()
    conn.close()
    
    if not history:
        return []
    return history