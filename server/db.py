import sqlite3

def get_db_connection():
    conn = sqlite3.connect('devices.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            os_name TEXT NOT NULL,
            os_version TEXT NOT NULL,
            installed_apps TEXT NOT NULL,
            online_timestamp TEXT NOT NULL,
            offline_timestamp TEXT,
            geolocation TEXT,
            watchlist INTEGER DEFAULT 0,
            allow_info_view INTEGER DEFAULT 0,
            allow_interaction_history_view INTEGER DEFAULT 0
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS interaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            details TEXT NOT NULL,
            timestamp TEXT NOT NULL, 
            FOREIGN KEY(device_id) REFERENCES devices(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user'))  -- Rol sadece 'admin' veya 'user' olabilir
        )
    ''')
    
    conn.commit()
    conn.close()

