import logging
from flask import Flask, request, jsonify, send_file, render_template
from models import add_device, get_all_devices, remove_device_from_watchlist, add_device_to_watchlist, update_offline_timestamp, get_device_by_id, update_allow_info_view, log_interaction, get_interaction_history, update_allow_interaction_history_view, update_online_timestamp,verify_user
import threading
import time
from db import create_tables
import os
from werkzeug.utils import secure_filename
from flask import session, redirect, url_for
from db import get_db_connection
from flask import flash
import bcrypt




logging.basicConfig(filename='server_log.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s:%(message)s')



interaction_logger = logging.getLogger('interaction_logger')
interaction_handler = logging.FileHandler('interaction_history.log')
interaction_handler.setLevel(logging.INFO)
interaction_formatter = logging.Formatter('%(asctime)s - %(message)s')
interaction_handler.setFormatter(interaction_formatter)
interaction_logger.addHandler(interaction_handler)


app = Flask(__name__)
app.secret_key = 'supersecretkey'


UPLOAD_FOLDER = 'uploaded_files/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


client_last_heartbeat = {}

create_tables()


@app.route('/')
def index():
    devices = get_all_devices()
    return render_template('index.html', devices=devices)

@app.route('/file_operations')
def file_operations():
    return render_template('file_operations.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = verify_user(username, password)
        
        if user:
            user_id, role = user
            session['user_id'] = user_id
            session['role'] = role
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password")
    else:
        return render_template('login.html')


def verify_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, password, role FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return user['id'], user['role']
    else:
        return None



@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash(f"Username '{username}' is already taken. Please choose another one.", "error")
            return render_template('register.html')

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        try:
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                           (username, hashed_password.decode('utf-8'), role))
            conn.commit()
            flash("Registration successful. You can now login.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('register.html', error="Registration failed")
        finally:
            conn.close()
    else:
        return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('index'))







@app.route('/register', methods=['POST'])
def register_device():
    data = request.get_json()
    user_id = data.get('user_id')
    os_name = data.get('os_name')
    os_version = data.get('os_version')
    installed_apps = data.get('installed_apps', 'N/A')
    online_timestamp = data.get('online_timestamp')
    geolocation = data.get('geolocation', 'Unknown')

    device_id = add_device(user_id, os_name, os_version, installed_apps, online_timestamp, geolocation)
    
    if device_id:
        add_device_to_watchlist(device_id)
        logging.info(f"Device {device_id} added to watchlist.")
        return jsonify({"message": "Device successfully registered and added to the watchlist!", "device_id": device_id}), 201
    else:
        logging.error("Device registration failed. No device ID returned.")
        return jsonify({"message": "Device registration failed."}), 500



@app.route('/devices', methods=['GET'])
def list_devices():
    user_id = session.get('user_id')
    role = session.get('role')
    
    logging.debug("Devices route requested")
    
    if role == 'admin':
        devices = get_all_devices(None)
    else:
        devices = get_all_devices(user_id)
    
    return render_template('devices.html', devices=devices, client_last_heartbeat=client_last_heartbeat, time=time)



@app.route('/heartbeat', methods=['POST'])
def receive_heartbeat():
    logging.debug("Heartbeat route requested")
    data = request.get_json()
    device_id = data.get('device_id')
    current_time = time.time()

    device = get_device_by_id(device_id)

    if device:
        if device['watchlist'] == 1:
            client_last_heartbeat[device_id] = current_time
            
            update_online_timestamp(device_id)
            
            logging.info(f"Heartbeat received from device {device_id}, watchlist status: added")
            return jsonify({"message": "Heartbeat received"}), 200
        else:
            logging.info(f"Device {device_id} removed from watchlist, stopping heartbeat.")
            return jsonify({"message": "Device removed from watchlist, stopping heartbeat."}), 200
    else:
        logging.warning(f"Device {device_id} not found")
        return jsonify({"message": "Device not found"}), 404





@app.route('/upload_file', methods=['POST'])
def upload_file():
    device_id = request.form.get('device_id')
    if not device_id:
        return jsonify({"message": "Device ID is required"}), 400
    
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if file:
        filename = secure_filename(f"{device_id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        logging.info(f"File '{filename}' uploaded from device {device_id}")
        interaction_logger.info(f"File '{filename}' uploaded from device {device_id}")

        log_interaction(device_id, "File-Uploaded", filename)

        return jsonify({"message": f"File '{filename}' uploaded successfully"}), 200



@app.route('/download_file/<filename>', methods=['GET'])
def download_file(filename):
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"message": "Device ID is required"}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f"{device_id}_{filename}"))

    if os.path.exists(file_path):
        logging.info(f"File '{filename}' downloaded by device {device_id}")
        return send_file(file_path, as_attachment=True)
    else:
        logging.error(f"File '{filename}' not found for device {device_id}")
        return jsonify({"message": "File not found"}), 404







@app.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    data = request.get_json()
    device_id = data.get('device_id')
    
    if device_id:
        add_device_to_watchlist(device_id)
        logging.info(f"Device {device_id} added to watchlist.")
        return jsonify({"message": f"Device {device_id} added to watchlist"}), 200
    return jsonify({"message": "Device ID is required"}), 400


@app.route('/remove_from_watchlist', methods=['POST'])
def remove_from_watchlist():
    data = request.get_json()
    device_id = data.get('device_id')
    
    if device_id:
        remove_device_from_watchlist(device_id)
        logging.info(f"Device {device_id} removed from watchlist.")
        return jsonify({"message": f"Device {device_id} removed from watchlist"}), 200
    return jsonify({"message": "Device ID is required"}), 400





@app.route('/watchlist_status', methods=['POST'])
def check_watchlist_status():
    data = request.get_json()
    device_id = data.get('device_id')

    device = get_device_by_id(device_id)
    
    if device:
        if device['watchlist'] == 1:
            logging.info(f"Device {device_id} is in watchlist.")
            return jsonify({"watchlist_status": "added"}), 200
        else:
            logging.info(f"Device {device_id} is not in watchlist.")
            return jsonify({"watchlist_status": "removed"}), 200
    else:
        logging.warning(f"Device {device_id} not found.")
        return jsonify({"message": "Device not found"}), 404








last_command = None


@app.route('/send_command', methods=['POST'])
def send_command():
    global last_command
    data = request.get_json()
    
    device_id = data.get('device_id')
    command = data.get('command')
    
    if device_id and command:
        last_command = command
        logging.info(f"Manual command received for device {device_id}: {command}")
        flash(f"Command '{command}' sent to device {device_id}", 'info')
    
        log_interaction(device_id, "Command-Sent", command)
        
        return jsonify({"message": f"Command '{command}' received for device {device_id}"}), 200
    else:
        logging.warning("Device ID or command missing")
        return jsonify({"message": "Device ID or command missing"}), 400


@app.route('/get_command', methods=['GET'])
def get_command():
    global last_command
    if last_command:
        command_to_send = last_command
        last_command = None 
        logging.info(f"Sending command: {command_to_send}")
        return jsonify({"command": command_to_send}), 200
    else:
        logging.warning("No command available to send")
        return jsonify({"message": "No command available"}), 404


@app.route('/send_command_result', methods=['POST'])
def send_command_result():
    data = request.get_json()
    
    device_id = data.get('device_id')
    command = data.get('command')
    result = data.get('result')
    
    if device_id and command and result:
        logging.info(f"Command executed for device {device_id}: {command}. Result: {result}")
        flash(f"Result for '{command}' on device {device_id}: {result}", 'success')
        
        log_interaction(device_id, "Command-Result", result)
        
        return jsonify({"message": "Command result received"}), 200
    else:
        logging.warning("Device ID, command or result missing in request")
        return jsonify({"message": "Device ID, command or result missing"}), 400








@app.route('/view_interaction_history/<device_id>', methods=['GET'])
def view_interaction_history(device_id):
    device = get_device_by_id(device_id)
    if device:
        if device['allow_interaction_history_view'] == 1:
            try:
                with open('interaction_history.log', 'r') as f:
                    interaction_history = f.readlines()
                return jsonify({"interaction_history": interaction_history}), 200
            except Exception as e:
                return jsonify({"message": f"Interaction history could not be read: {str(e)}"}), 500
        else:
            return jsonify({"message": "You are not allowed to view this interaction history."}), 403
    else:
        return jsonify({"message": "Device not found."}), 404




@app.route('/allow_interaction_view', methods=['POST'])
def allow_interaction_view():
    data = request.get_json()
    device_id = data.get('device_id')
    allow_view = data.get('allow_interaction_history_view', 0)

    if device_id is not None:
        update_allow_interaction_history_view(device_id, allow_view)
        logging.info(f"Device {device_id} interaction view permission updated to {allow_view}.")
        return jsonify({"message": f"Device {device_id} interaction history view permission updated."}), 200
    else:
        logging.warning("Device ID is missing in request.")
        return jsonify({"message": "Device ID is required"}), 400



@app.route('/check_interaction_history_permission/<device_id>', methods=['GET'])
def check_interaction_history_permission(device_id):
    device = get_device_by_id(device_id)
    if device:
        return jsonify({"allow_interaction_history_view": device['allow_interaction_history_view']}), 200
    else:
        return jsonify({"message": "Device not found"}), 404




@app.route('/logs')
def view_logs():
    try:
        with open('server_log.log', 'r') as f:
            logs = f.readlines()
        return render_template('logs.html', logs=logs)
    except Exception as e:
        return jsonify({"message": f"Loglar okunamadı: {str(e)}"}), 500



def check_client_status():
    while True:
        current_time = time.time()
        for device_id, last_heartbeat in client_last_heartbeat.items():
            time_difference = current_time - last_heartbeat
            if time_difference > 30:
                logging.warning(f"Client {device_id} is offline. Time difference: {time_difference}")
                update_offline_timestamp(device_id, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            else:
                logging.info(f"Client {device_id} is online. Time difference: {time_difference}")
                update_online_timestamp(device_id)
        time.sleep(10)






@app.route('/allow_info_view', methods=['POST'])
def allow_info_view():
    data = request.get_json()
    device_id = data.get('device_id')
    allow_view = data.get('allow_info_view', 0)
    
    if device_id is not None:
        update_allow_info_view(device_id, allow_view)
        logging.info(f"Device {device_id} information view permission updated to {allow_view}.")
        return jsonify({"message": f"Device {device_id} information view permission updated."}), 200
    else:
        logging.warning("Device ID is missing in request.")
        return jsonify({"message": "Device ID is required"}), 400

@app.route('/view_device_info/<device_id>', methods=['GET'])
def view_device_info(device_id):
    device = get_device_by_id(device_id)
    
    if device:
        if device['allow_info_view'] == 1:
            return jsonify({
                "os_name": device['os_name'],
                "os_version": device['os_version'],
                "installed_apps": device['installed_apps'],
                "online_timestamp": device['online_timestamp'],
                "geolocation": device['geolocation']
            }), 200
        else:
            return jsonify({"message": "You are not allowed to view this information."}), 403
    else:
        return jsonify({"message": "Device not found."}), 404



@app.route('/get_interaction_history/<int:device_id>', methods=['GET'])
def get_interaction_history_route(device_id):
    device = get_device_by_id(device_id)
    
    if device:
        if device['allow_interaction_history_view'] == 1:
            try:
                history = get_interaction_history(device_id)
                if not history:
                    logging.info(f"No interaction history found for device {device_id}")
                    return jsonify({"interaction_history": []}), 200
                interaction_history = [
                    {
                        "interaction_type": row["interaction_type"],
                        "details": row["details"],
                        "timestamp": row["timestamp"]
                    }
                    for row in history
                ]
                return jsonify({"interaction_history": interaction_history}), 200
            except Exception as e:
                logging.error(f"Error fetching interaction history for device {device_id}: {str(e)}")
                return jsonify({"message": f"Interaction history could not be retrieved: {str(e)}"}), 500
        else:
            return jsonify({"message": "You are not allowed to view this interaction history."}), 403
    else:
        return jsonify({"message": "Device not found."}), 404










if __name__ == '__main__':
    threading.Thread(target=check_client_status, daemon=True).start()
    logging.info("Server started")
    app.run(host='0.0.0.0', port=5050, debug=True)