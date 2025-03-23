import eventlet
eventlet.monkey_patch()
import codecs
from werkzeug.utils import secure_filename
import configparser
import glob
import json
import os
import queue
import sys
import threading
import time
import webbrowser
import argparse
from flask import Flask, render_template
from flask import request, jsonify, send_from_directory, Response  # 引入包中要使用的类
from flask_cors import CORS
from flask_socketio import SocketIO
from rich.console import Console
import shutil
import getNum
from CCRS_Library import (
    ServerGUI,
    check_and_create_database,
    insert_hub_info,
    query_hub_info_by_mold_number,
    query_mold_info_by_number,
    query_all_hub_info,
    execute_custom_sql,
    flask_send_sysInfo,
)

current_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(current_dir, "app.log")
logSwitch = "true"
log_queue = queue.Queue()
debug = "false"
host = ""
database_file = "./db/data.db"
port = ""
UPLOAD_FOLDER = ""
use_https = False
API = {
    "isHTTPS": "isHTTPS",
    "clear": "clear",
    "getpicture": "getpicture",
    "start": "start",
    "upload": "upload",
    "test": "test",
    "info": "info",
}
# 定义命令列表
commands = ["help", "blacklist", "sql", "server"]
command_blacklist = ["drop table", "truncate", "delete from", "update"]
sys_info = {}


def sql_help(_):
    help = """
        If there are no extended commands, the operation will be executed directly.
        Tables included in the database: hub_info, mold_info
        "--help": Show help.
        "--check_sql": Check the database, no parameters required.
        "--insert": The mold number to be inserted.
        "--lun-gu-info-model": Query the recognition records of the specified mold number.
        "--mo-ju-jinfo-model": Query the mold information of the specified mold number.
        "--query_all_hub_info": Quick query without parameters.
        "--execute_custom_sql": Execute a custom SQL statement (bypass the blacklist).
        """
    return help


sql_command_map = {
    "--help": (sql_help, "none"),
    "--check_sql": (
        check_and_create_database,
        "none",
    ),  # Check the database, no parameters
    "--insert": (insert_hub_info, "mold_number: The mold number to be inserted"),
    "--lun-gu-info-model": (
        query_hub_info_by_mold_number,
        "mold_number: The mold number to query",
    ),
    "--mo-ju-jinfo-model": (
        query_mold_info_by_number,
        "mold_number: The mold number to query",
    ),
    "--query_all_hub_info": (query_all_hub_info, "none"),
    "--execute_custom_sql": (execute_custom_sql, "command: Custom SQL statement"),
}
mode = "nomal"
# 存储客户端的 UUID 和 socket ID 的映射关系
clients_lock = threading.Lock()
clients = {}
# 用于通知主线程 GUI 已经成功创建的事件
gui_created_event = threading.Event()
gui = None


def log_writer():
    """
    日志写入线程函数，从队列中取出日志数据并写入文件
    """
    while True:
        log_data = log_queue.get()
        if log_data is None:
            break
        first_log = log_data.pop("first_log")
        if not first_log:
            # 将日志数据写入文本文件，以追加模式
            with codecs.open("server.log", "a", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write("\n")
        else:
            with codecs.open("server.log", "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write("\n")
        log_queue.task_done()


def log_event(event, result, remark=None, first_log=False):
    remark = "" if remark is None else remark
    if logSwitch.lower() == "true":
        log_data = {
            "timestamp": time.strftime("%H:%M:%S"),
            "event": event,
            "result": result,
            "remark": remark,
            "first_log": first_log,
        }
        if result != "successfully":
            send_message_to_client(
                f"Server error executing {log_data['event']}, severity {log_data['result']}, remarks{log_data['remark']}"
            )
        if gui is not None:
            gui.log_event(log_data)
            gui.refresh_GUI()
        log_queue.put(log_data)


class ConfigManager:
    def __init__(self, config_file="config.ini"):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        if not os.path.exists(self.config_file):
            self.config.add_section("Settings")
            self.config.add_section("SSH_Service")
            self.config.add_section("API_Service")

            with open(self.config_file, "w") as configfile:
                configfile.write(
                    "# This is a server configuration file. Any modifications require a server restart to take effect.\n"
                )

                # Settings
                configfile.write("[Settings]\n")
                configfile.write('host = 127.0.0.1\n')
                configfile.write('port = 5000\n')
                configfile.write('debug = false\n')
                configfile.write('logSwitch = true\n')

                # SSH_Service
                configfile.write("\n[SSH_Service]\n")
                configfile.write('use_https = false\n')
                configfile.write('ssh_path = ./CRT\n')

                # API_Service
                configfile.write("\n[API_Service]\n")
                configfile.write('USE_OPTIONS = false\n')
                configfile.write('isHTTPS = isHTTPS\n')
                configfile.write('clear = clear\n')
                configfile.write('getpicture = getpicture\n')
                configfile.write('start = start\n')
                configfile.write('upload = upload\n')
                configfile.write('test = test\n')
                configfile.write('info = info\n')

        else:
            self.config.read(self.config_file)


    def get(self, section, option):
        try:
            log_event("Server-Setting Service", "successfully", f"{section}>{option}")
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            log_event("Server-Setting Service", "warning", f"{section}>{option}")
            return None

    def get_with_default(self, section, option, default=None):
        try:
            log_event("Server-Setting Service", "successfully", f"{section}>{option}")
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            log_event("Server-Setting Service", "warning", f"{section}>{option}")
            return default

    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        log_event(
            "Server-Setting Service",
            "successfully",
            f"write {section}>{option} = {value}",
        )
        self.config.set(section, option, value)
        with open(self.config_file, "w") as configfile:
            self.config.write(configfile)

    def remove_option(self, section, option):
        if self.config.has_section(section) and self.config.has_option(section, option):
            self.config.remove_option(section, option)
            log_event(
                "Server-Setting Service", "successfully", f"del {section}>{option} "
            )
            with open(self.config_file, "w") as configfile:
                self.config.write(configfile)


config_manager = ConfigManager()
console = Console()
app = Flask(
    __name__,
    static_url_path="/",
    static_folder="./flask-dist",
    template_folder="./flask-dist",
)

# 配置 Flask-SocketIO 允许跨域
socketios = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_interval=2,
    ping_timeout=60,
)


def delete_files_in_folder(folder_path="./flask-dist/UPLOAD", filename=None):
    """删除指定文件夹下的所有文件或指定文件

    Args:
      folder_path: 要删除文件的文件夹路径
      filename: 要删除的文件名（可选）
    """
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if (
                filename and file != filename
            ):  # 如果指定了文件名，且当前文件不是指定的文件，则跳过
                continue
            try:
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            except OSError as e:
                print(f"Error deleting file {file_path}: {e}")


def blacklist_operations(command):
    if "--help" in command:
        return jsonify(
            "Available parameters are: --help to display available parameters, --add to temporarily add a blacklist command to the backlist list, --remove to temporarily remove a command from the blacklist, --show to display the blacklist instructions (by default, no parameters also means displaying the blacklist instructions)."
        )
    if "--add" in command:
        command_blacklist.append(command.split("--add")[1].strip())
        log_event("Server-SQL blacklist", "successfully", f"add {command}")
        return jsonify(
            f"Successfully added '{command.split('--add')[1].strip()}' to the blacklist."
        )
    if "--remove" in command:
        if command.split("--remove")[1].strip() in command_blacklist:
            command_blacklist.remove(command.split("--remove")[1].strip())
            log_event("Server-SQL blacklist", "successfully", f"remove {command}")
            return jsonify(
                f"Successfully removed '{command.split('--remove')[1].strip()}' from the blacklist."
            )
        return f"'{command.split('--remove')[1].strip()}' is not in the blacklist and cannot be removed."
    elif "--show" in command or not any(
        arg in command for arg in ["--add", "--remove", "--help"]
    ):
        return jsonify(f"Current blacklist: {command_blacklist}")
    else:
        return jsonify("Invalid blacklist operation command.")


# 执行SQL命令的函数
def execute_sql(command):
    for keyword in command_blacklist:
        if keyword in command.lower():
            log_event(
                "Server-SQL blacklist", "warning", f"Can`t run {command} with SQL"
            )
            return jsonify(f"Commands containing '{keyword}' are prohibited.")

    # Match commands and parameters
    for cmd, (func, params_desc) in sql_command_map.items():
        if command.startswith(cmd):
            args = command[len(cmd) :].strip()  # Get the parameter part
            if params_desc == "none" and args:
                log_event(
                    "Server-SQL service", "warning", f"Unacceptable parameter for {cmd}"
                )
                return jsonify(f"Command {cmd} does not accept parameters.")
            try:
                if params_desc != "none":
                    log_event("Server-SQL service", "successfully")
                    result = func(database_file, args)
                else:
                    log_event("Server-SQL service", "successfully")
                    result = func(database_file)
                return jsonify(result)
            except Exception as e:
                log_event("SQL service", "error", str(e))
                return jsonify(f"Command execution failed: {str(e)}")

    return jsonify(execute_custom_sql(database_file, command))


@app.route("/")
def mainPage():
    return render_template("index.html")


@app.route(f'/ {API["isHTTPS"]}')
def isHTTPS():
    return jsonify(port == 443), 200


@app.route(f'/{API["clear"]}')
def clear_files():
    filename = request.args.get("filename")  # 从请求参数中获取文件名
    delete_files_in_folder(filename=filename)
    return jsonify("Delete"), 200


@app.route(f'/{API["getpicture"]}', methods=["GET"])
def getpic():
    try:
        filename = request.args.get("name")
        if not filename:
            log_event(
                "Server-File Service", "warning", f"FileName:{filename} was Invalid"
            )
            return jsonify({"error": "No filename provided"}), 400

        # 确保文件存在
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            log_event(
                "Server-File Service",
                "error",
                f"The file {file_path} you are looking for does not exist",
            )
            return jsonify({"error": "File does not exist"}), 404

        # 确保 Flask 应用有权限读取文件
        if not os.access(file_path, os.R_OK):
            log_event(
                "Server-File Service",
                "error",
                f"File {file_path} read permission denied",
            )
            return jsonify({"error": "File is not readable"}), 403

        # 返回图片文件
        log_event("Server-File Service", "successfully", "successfully")
        return send_from_directory(UPLOAD_FOLDER, filename)

    except Exception as e:
        log_event(
            "Server-File Service", "error", f"An unhandled exception occurred: {str(e)}"
        )
        return jsonify({"error": "Internal server error"}), 500


@app.route(f'/{API["start"]}', methods=["GET"])
def start():
    try:
        client_uuid = request.args.get("uuid")
        if not client_uuid or client_uuid not in clients:
            return jsonify({"error": "Invalid Client ID"}), 403

        # 构建UUID对应的文件路径
        uuid_file = os.path.join(UPLOAD_FOLDER, secure_filename(client_uuid))
        if not os.path.exists(uuid_file):
            return jsonify(
                {"error": "The upload file for this client was not found. "}
            ), 404

        # 处理特定客户端的文件
        text = getNum.New_auto_run(uuid_file)  # 将文件路径传入处理函数
        # 处理完成后删除对应的UUID文件
        # delete_files_in_folder(UPLOAD_FOLDER, filename=secure_filename(client_uuid))
        log_event(
            "Server-OCR Service",
            "successfully",
            f"Client {client_uuid} processing result: {text}",
        )
        insert_hub_info(db_file=database_file, mold_number=text)
        return jsonify([text]), 200

    except Exception as e:
        log_event("Server-OCR Service", "error", f"Processing failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route(f'/{API["upload"]}', methods=["POST"])
def upload_file():
    try:
        client_uuid = request.args.get("uuid")
        if not client_uuid or client_uuid not in clients:
            return jsonify({"error": "Invalid Client ID"}), 403

        files = request.files
        print(f"Received files: {files}")  # 调试信息
        for file in files:
            if file and files[file].filename != "":
                filename = secure_filename(client_uuid)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                print(f"Saving file to: {file_path}")  # 调试信息
                files[file].save(file_path)

        log_event(
            "Server-Upload Service", "successfully", f"Client {client_uuid} Upload File"
        )
        return jsonify({"message": f"The file has been saved as {filename}"})

    except Exception as e:
        log_event("Server-Upload Service", "error", f"File acceptance failed:{e}")
        print(f"Error: {e}")  # 打印异常信息
        return jsonify({"error": str(e)}), 500


@app.route(f'/{API["test"]}')
def test():
    log_event("Server-Communication Detection Service", "successfully")
    return jsonify("You already connect the server now!")


@app.route(f'/{API["info"]}')
def return_info():
    file_num = 0
    file_list = []
    for fn in os.listdir("./flask-dist/UPLOAD"):  # fn 表示的是文件名
        file_name = []
        url = "https" if use_https else "http" + "://{host}:{port}/getpicture?name={fn}"
        fsize = (
            str(round(os.path.getsize("./flask-dist/UPLOAD/" + fn) / 1024 / 1024, 2))
            + "MiB"
        )
        file_num = file_num + 1
        file_name.append(url)
        file_name.append(fn)
        file_name.append(fsize)
        file_list.append(file_name)
    log_event("Server-File Service", "successfully")
    return jsonify({"file_count": file_num, "file_list": file_list, "API": API}), 200


@app.errorhandler(404)
def page404(e):
    return render_template("/error_page/404.html"), 404


def print_info(host, port, elseinfo=""):
    os.system("cls" if os.name.lower() == "nt" else "clear")
    if port == 443:
        print(f"Server will running at https://{host}/")
        if debug == "false":
            webbrowser.open(f"https://{host}/")
    else:
        print(f"Server will running at http://{host}:{port}")
        if debug == "false":
            webbrowser.open(f"http://{host}:{port}")
    print(elseinfo)


# 获取日志 API
@app.route("/getlogs", methods=["GET"])
def get_logs():
    try:
        if logSwitch.lower() == "true":
            logs = []
            with codecs.open("server.log", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    try:
                        data = json.loads(line)
                        logs.append(data)
                    except json.JSONDecodeError as e:
                        # 记录解析失败的行和错误信息
                        log_event(
                            "Server-log parsing error",
                            "error",
                            f"Failed to parse line: '{line}', Error: {e}",
                        )
                        continue

            # 使用 json.dumps 来确保返回 JSON 数据时不转义中文
            response_data = json.dumps(logs, ensure_ascii=False)
            return Response(response_data, mimetype="application/json; charset=utf-8")
        log_event(
            "Server-logging error",
            "warning",
            "The front end attempts to read the log, but is rejected by the server",
        )
        return jsonify(
            {
                "message": "Log access is denied. Try to enable log query service in the configuration file."
            }
        )
    except Exception as e:
        log_event("SERVER CANNOT READ LOGS", "error", e)


def get_ssl_files_paths(ssh_path, key_ext=".key", crt_ext=".crt"):
    """
    从指定文件夹中查找并返回扩展名为.key和.crt的文件的完整路径。

    Args:
        ssh_path (str): 需要搜索的文件夹路径。
        key_ext (str, optional): .key文件扩展名。默认为'.key'。
        crt_ext (str, optional): .crt文件扩展名。默认为'.crt'。

    Returns:
        tuple: 包含.key文件和.crt文件完整路径的元组。

    Raises:
        FileNotFoundError: 如果未找到指定扩展名的文件。
    """

    # 确保ssh_path是绝对路径
    ssh_path = os.path.abspath(ssh_path)

    # 查找所有符合扩展名的文件
    key_files = glob.glob(os.path.join(ssh_path, f"*{key_ext}"))
    crt_files = glob.glob(os.path.join(ssh_path, f"*{crt_ext}"))

    # 如果找到多个文件，这里可以加入额外的逻辑来选择具体的文件
    key_file_path = key_files[0] if key_files else ""
    crt_file_path = crt_files[0] if crt_files else ""

    return key_file_path, crt_file_path


@app.route("/getdatabase")
def get_database():
    hub_info_results = query_all_hub_info(database_file)
    return jsonify({"result": hub_info_results}), 200


@app.route("/command", methods=["GET"])
def run_command():
    global mode
    command = request.args.get("command")
    try:
        if mode == "sql":
            if command.lower() == "exit":
                mode = "normal"
                return jsonify("Exit SQLite")
            result = execute_sql(command)
            return result
        else:
            if command.lower().startswith("help"):
                return jsonify(
                    "Available commands: help (display help information), blacklist (perform blacklist-related operations, can include parameters like --help, etc.), sql (enter standalone SQL execution mode, type 'exit' to return to normal mode)"
                )
            if command.lower().startswith("blacklist"):
                return blacklist_operations(command)
            if "sql" in command.lower():
                mode = "sql"
                print(
                    "Entered SQL execution mode. Type 'exit' to return to normal mode."
                )
                return jsonify(
                    "Entered SQL execution mode. Type 'exit' to return to normal mode. You can enter --help to view help."
                )
            if "exit" in command.lower():
                return jsonify("Returned to normal mode.")
            return jsonify("Invalid command. Please enter a valid command.")
    except Exception as e:
        log_event("Server-SERVER CANNOT RUN COMMAND", "warning", e)
        return jsonify(f"An error occurred: {str(e)}")

@app.route("/adduuid",methods=['GET'])
def add_uuid():
    uuid=request.args.get('uuid')
    try:
        with clients_lock:
            if uuid not in clients:
                clients[uuid]="API-"+uuid
                gui.queue.put({"event": "New device", "UUID": uuid, "aID": "API-"+uuid})
            else:
                pass
            return jsonify({"result": clients[uuid]}), 200
    except Exception as e:
        log_event('Server-SERVER CANNOT REGISTER', 'error',e)

@app.route("/removeuuid",methods=['GET'])
def remove_uuid():
    uuid=request.args.get('uuid')
    try:
        with clients_lock:
            del clients[uuid]
        log_event(f"Server-Client {uuid} disconnected", 'info')
    except Exception as e:
        log_event('Server-SERVER CANNOT Remove UUID', 'error',e)
    return jsonify({"result": clients[uuid]}), 200

# 监听客户端注册事件（传递 UUID）
@socketios.on("register")
def handle_register(data):
    try:
        with clients_lock:
            client_uuid = data["uuid"]
            if client_uuid not in clients:
                clients[client_uuid] = request.sid
                gui.queue.put({"event": "New device", "UUID": data['uuid'], "aID": request.sid})
                send_message_to_client('Client registered successfully', client_uuid)
            else:
                pass
    except Exception as e:
        log_event('Server-SERVER CANNOT REGISTER', 'error', e)


@socketios.on("disconnect")
def handle_disconnect():
    uuid = None
    # 查找断开连接的客户端的 uuid，并将其从 clients 中移除
    for key, value in clients.items():
        if value == request.sid:
            uuid = key
            break
    if uuid:
        del clients[uuid]  # 删除该客户端的连接信息
    log_event(f"Server-Client {uuid} disconnected",'info')


# 发送消息到指定客户端
def send_message_to_client(message, client_uuid=None):
    try:
        if (
            isinstance(client_uuid, str) and len(client_uuid) > 0
        ):  # Ensure UUID is a string
            if client_uuid in clients:
                sid = clients[client_uuid]
                socketios.emit("new_message", {"message": message}, to=sid)
                print(f"Message sent to client {client_uuid}")
            else:
                print(f"Client {client_uuid} not found")
        elif client_uuid is None:  # Broadcast message to all online clients
            for uuid, sid in clients.items():
                socketios.emit("new_message", {"message": message}, to=sid)
            print(f"Message broadcasted to {len(clients)} clients")
        else:
            pass
    except Exception as e:
        log_event("Server-SERVER SEND MESSAGE FAILED", "error", str(e))
        raise


def init():
    # Retrieve user configuration file information
    global host, port, UPLOAD_FOLDER, API, debug, logSwitch, gui, use_https
    log_event("Server-Configuration Reading Service", "successfully", first_log=True)

    check_and_create_database(database_file)

    host = config_manager.get_with_default("Settings", "host", "127.0.0.1")
    logSwitch = config_manager.get_with_default("Settings", "logSwitch", "true")
    port = config_manager.get_with_default("Settings", "port", "5000")
    debug = config_manager.get_with_default("Settings", "debug", "false")

    use_https = (
        not config_manager.get_with_default("SSH_Service", "use_https", "false").lower()
        == "false"
    )
    ssh_key, ssh_crt = get_ssl_files_paths(
        config_manager.get_with_default("SSH_Service", "ssh_path", "./CRT")
    )

    if config_manager.get_with_default("API_Service", "USE_OPTIONS", "false") == "true":
        API["isHTTPS"] = config_manager.get_with_default(
            "API_Service", "isHTTPS", "isHTTPS"
        )
        API["clear"] = config_manager.get_with_default("API_Service", "clear", "clear")
        API["getpicture"] = config_manager.get_with_default(
            "API_Service", "getpicture", "getpicture"
        )
        API["start"] = config_manager.get_with_default("API_Service", "start", "start")
        API["upload"] = config_manager.get_with_default(
            "API_Service", "upload", "upload"
        )
        API["test"] = config_manager.get_with_default("API_Service", "test", "test")
        API["info"] = config_manager.get_with_default("API_Service", "info", "info")
        log_event(
            "Server-Configuration Reading Service",
            "warning",
            "API configuration has changed, please update the front-end accordingly",
        )

    UPLOAD_FOLDER = "flask-dist/UPLOAD"
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    delete_files_in_folder()

    if ssh_key != "" and ssh_crt != "":
        if use_https:
            log_event(
                "Server-Configuration Reading Service",
                "successfully",
                "HTTPS process started!",
            )
        else:
            log_event(
                "Server-Configuration Reading Service",
                "successfully",
                "It looks like you support HTTPS, you can enable it anytime!",
            )
    else:
        log_event(
            "Server-Configuration Reading Service",
            "successfully",
            "Server started successfully!",
        )

    log_event(
        "Server-SERVER START SUCCESS", "successfully", "Server started successfully"
    )
    print("SERVER START SUCCESS")

    CORS(app)

    if use_https:
        context = (f"{ssh_crt}", f"{ssh_key}")
        socketios.run(
            debug=debug == "true",
            host=host,
            port=443,
            app=app,
            allow_unsafe_werkzeug=True,
            ssl_context=context,
        )
    else:
        socketios.run(
            debug=debug == "true",
            host=host,
            port=int(port),
            app=app,
            allow_unsafe_werkzeug=True,
        )


def run_gui():
    """启动 GUI 界面"""
    global gui
    host = config_manager.get_with_default("Settings", "host", "127.0.0.1")
    logSwitch = config_manager.get_with_default("Settings", "logSwitch", "true")
    port = config_manager.get_with_default("Settings", "port", "5000")
    use_https = (
        not config_manager.get_with_default("SSH_Service", "use_https", "false").lower()
        == "false"
    )

    # 创建 GUI 实例
    gui = ServerGUI(
        server_url=f"https://{host}" if use_https else f"http://{host}:{port}",
        use_https=use_https,
        ssh_path=config_manager.get_with_default("SSH_Service", "ssh_path", "./CRT"),
        AdvanceAPISetting=config_manager.get_with_default(
            "API_Service", "USE_OPTIONS", "false"
        ) == "true",
        logSwitch=logSwitch,
        client_func=get_clients,
    )
    gui_created_event.set()

    try:
        gui.showGUI()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        gui.stop()


def get_clients():
    """获取当前的 clients 列表"""
    with clients_lock:
        return dict(clients)


# 主功能处理
def main(args):
    # 备份数据库
    if args.COPYDATABASE:
        source_path = "./db/data.db"
        destination_path = args.COPYDATABASE[0]
        try:
            if os.path.isdir(destination_path):
                # 如果目标路径是目录，构造目标文件路径
                destination_path = os.path.join(
                    destination_path, os.path.basename(source_path)
                )
            shutil.copy(source_path, destination_path)
            print(f"File copied successfully to {destination_path}")
        except FileNotFoundError:
            print(f"Source file not found: {source_path}")
        except PermissionError:
            print(f"Permission denied: {destination_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
    # 复制数据库
    if args.LOADDATABASE:
        source_path = "./db/data.db"
        destination_path = args.LOADDATABASE[0]
        try:
            if os.path.isdir(source_path):
                print(
                    "You must specify the address of the database file, not the directory containing the database file"
                )
                return 0
            shutil.copy(destination_path, source_path)
            print(f"File copied successfully from {destination_path}")
        except FileNotFoundError:
            print(f"Source file not found: {source_path}")
        except PermissionError:
            print(f"Permission denied: {destination_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
    # 切割图片
    if args.CUTIMAGEFROMDIR:
        source_dir = args.CUTIMAGEFROMDIR[0]
        save_dir = (
            args.CUTIMAGEFROMDIR[1]
            if len(args.CUTIMAGEFROMDIR) > 1
            else os.path.join(source_dir, "Save")
        )
        print("Command: CUTIMAGEFROMDIR")
        print(f"Source Directory: {source_dir}")
        print(f"Save Directory: {save_dir}")
        getNum.quick_cut_img(source_dir, save_dir)

    # 处理图片
    if args.PROCESSIMAGEDIR:
        source_dir = args.PROCESSIMAGEDIR[0]
        save_dir = args.PROCESSIMAGEDIR[1] if len(args.PROCESSIMAGEDIR) > 1 else None
        print("Command: PROCESSIMAGEDIR")
        print(f"Source Directory: {source_dir}")
        print(f"Save Directory: {save_dir if save_dir else 'Not specified'}")
        getNum.process_image(source_dir, save_dir)

    # 启动服务器
    if not any(
        [
            args.CUTIMAGEFROMDIR,
            args.PROCESSIMAGEDIR,
            args.COPYDATABASE,
            args.LOADDATABASE,
        ]
    ):
        print("Server Starting...")
        try:
            monitor_system_thread = threading.Thread(
                target=flask_send_sysInfo,
                args=(
                    socketios,
                    get_clients,
                ),
            )  # 创建监控线程
            monitor_system_thread.daemon = True  # 设置为守护线程，主线程退出时自动退出
            monitor_system_thread.start()  # 启动监控线程

            writer_thread = threading.Thread(target=log_writer, daemon=True)
            writer_thread.daemon = True
            writer_thread.start()

            if not args.nogui:
                flask_thread = threading.Thread(target=init, daemon=True)
                flask_thread.daemon = True
                flask_thread.start()
            else:
                init()
                return 0

            if args.simulate:
                if not args.nogui:
                    flask_gui = threading.Thread(target=run_gui, daemon=True)
                    flask_gui.start()
                time.sleep(5)
                print("Simulation complete. Exiting...")
                return 0
            run_gui()

        except Exception as e:
            log_event("SERVER STATUS", "error", e)
            print(f"SERVER STATUS error: {e}")
            return 1

    return 0


# 初始化参数解析器
def create_parser():
    parser = argparse.ArgumentParser(description="CCRS Tool")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simulate the startup process without running the GUI.",
    )
    parser.add_argument(
        "--nogui", action="store_true", help="Start server without GUI."
    )
    parser.add_argument(
        "--CUTIMAGEFROMDIR",
        nargs="+",
        metavar=("SOURCE_DIR", "SAVE_DIR"),
        help="Cut images from a directory.",
    )
    parser.add_argument(
        "--PROCESSIMAGEDIR",
        nargs="+",
        metavar=("SOURCE_DIR", "SAVE_DIR"),
        help="Process images in a directory.",
    )
    parser.add_argument(
        "--COPYDATABASE",
        nargs="+",
        metavar="SAVE_DIR",
        help="Copy database from source to destination.",
    )
    parser.add_argument(
        "--LOADDATABASE",
        nargs="+",
        metavar="Source_DIR",
        help="Copy the database from the source to the DATABASE directory and then use it the next time the program starts. Note: This operation overwrites the original database file!",
    )
    return parser


if __name__ == "__main__":
    # 解析命令行参数
    parser = create_parser()
    args = parser.parse_args()

    # 调用主函数并传递参数
    exit_code = main(args)

    # 退出程序
    sys.exit(exit_code)
