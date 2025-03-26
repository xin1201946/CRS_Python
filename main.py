import uuid
from concurrent.futures import ThreadPoolExecutor

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
    insert_recognition_record,
    query_recognition_record_by_mold_number,
    query_mold_info_by_number,
    query_all_recognition_record,
    execute_custom_sql,
    flask_send_sysInfo,
)
from concurrent.futures import ProcessPoolExecutor

# 获取当前脚本的绝对路径，并提取所在目录
# Get the absolute path of the current script and extract the directory where it is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# 定义日志文件的路径
# Define the path of the log file
log_file = os.path.join(current_dir, "app.log")
# 日志开关，默认为开启
# Log switch, default is on
logSwitch = "true"
# 日志队列，用于存储日志数据
# Log queue, used to store log data
log_queue = queue.Queue()
# 调试模式开关，默认为关闭
# Debug mode switch, default is off
debug = "false"
# 服务器主机地址
# Server host address
host = ""
# 数据库文件路径
# Database file path
database_file = "./db/data.db"
# 服务器端口号
# Server port number
port = ""
# 文件上传目录
# File upload directory
UPLOAD_FOLDER = ""
# 是否使用 HTTPS，默认为 False
# Whether to use HTTPS, default is False
use_https = False
# API 接口配置
# API interface configuration
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
# Define the command list
commands = ["help", "blacklist", "sql", "server"]
# SQL 命令黑名单
# SQL command blacklist
command_blacklist = ["drop table", "truncate", "delete from", "update"]
# 系统信息
# System information
sys_info = {}


def sql_help(_):
    """
    显示 SQL 命令帮助信息
    Display SQL command help information
    """
    help = """
        If there are no extended commands, the operation will be executed directly.
        Tables included in the database: recognition_record, mold_info
        "--help": Show help.
        "--check_sql": Check the database, no parameters required.
        "--insert": The mold number to be inserted.
        "--history-records": Query the recognition records of the specified mold number.
        "--mo-ju-jinfo-model": Query the mold information of the specified mold number.
        "--query_all_recognition_record": Quick query without parameters.
        "--execute_custom_sql": Execute a custom SQL statement (bypass the blacklist).
        如果没有扩展命令，将直接执行操作。
        数据库中包含的表：recognition_record, mold_info
        "--help": 显示帮助信息。
        "--check_sql": 检查数据库，无需参数。
        "--insert": 要插入的模具编号。
        "--history-records": 查询指定模具编号的识别记录。
        "--mo-ju-jinfo-model": 查询指定模具编号的模具信息。
        "--query_all_recognition_record": 无参数快速查询。
        "--execute_custom_sql": 执行自定义 SQL 语句（绕过黑名单）。
        """
    return help


# SQL 命令映射表
# SQL command mapping table
sql_command_map = {
    "--help": (sql_help, "none"),
    "--check_sql": (
        check_and_create_database,
        "none",
    ),  # 检查数据库，无需参数
    "--insert": (insert_recognition_record, "mold_number: The mold number to be inserted"),
    "--history-records": (
        query_recognition_record_by_mold_number,
        "mold_number: The mold number to query",
    ),
    "--mo-ju-jinfo-model": (
        query_mold_info_by_number,
        "mold_number: The mold number to query",
    ),
    "--query_all_recognition_record": (query_all_recognition_record, "none"),
    "--execute_custom_sql": (execute_custom_sql, "command: Custom SQL statement"),
}
# 运行模式，默认为正常模式
# Operating mode, default is normal mode
mode = "nomal"
# 存储客户端的 UUID 和 socket ID 的映射关系
# Store the mapping relationship between client UUID and socket ID
clients_lock = threading.Lock()
clients = {}
# 用于通知主线程 GUI 已经成功创建的事件
# Event used to notify the main thread that the GUI has been successfully created
gui_created_event = threading.Event()
# GUI 对象，初始为 None
# GUI object, initially None
gui = None

# 任务队列，最多容纳 50 个任务
# Task queue, can hold up to 50 tasks
task_queue = queue.Queue(maxsize=50)
# 线程池执行器，最多 20 个工作线程
# Thread pool executor, up to 20 worker threads
executor = ThreadPoolExecutor(max_workers=20)
# executor = ProcessPoolExecutor(max_workers=20)
# 保存任务 UUID 与对应的 Future 对象
# Save the task UUID and the corresponding Future object
jobs = {}
# 任务状态字典
# Task status dictionary
jobs_status = {}  # {task_uuid: "waiting" | "processing" | "completed" | "failed"}


def log_writer():
    """
    日志写入线程函数，从队列中取出日志数据并写入文件
    Log writing thread function, take log data from the queue and write it to the file
    """
    while True:
        # 从日志队列中获取日志数据
        # Get log data from the log queue
        log_data = log_queue.get()
        if log_data is None:
            break
        # 取出是否为第一条日志的标志
        # Take out the flag indicating whether it is the first log
        first_log = log_data.pop("first_log")
        if not first_log:
            # 将日志数据写入文本文件，以追加模式
            # Write log data to a text file in append mode
            with codecs.open("server.log", "a", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write("\n")
        else:
            with codecs.open("server.log", "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write("\n")
        # 标记任务完成
        # Mark the task as completed
        log_queue.task_done()


def log_event(event, result, remark=None, first_log=False):
    """
    记录日志事件
    Record log events
    """
    # 如果备注为空，设置为空字符串
    # If the remark is empty, set it to an empty string
    remark = "" if remark is None else remark
    if logSwitch.lower() == "true":
        # 构建日志数据
        # Build log data
        log_data = {
            "timestamp": time.strftime("%H:%M:%S"),
            "event": event,
            "result": result,
            "remark": remark,
            "first_log": first_log,
        }
        if result != "successfully":
            # 发送错误消息给客户端
            # Send an error message to the client
            send_message_to_client(
                f"Server error executing {log_data['event']}, severity {log_data['result']}, remarks{log_data['remark']}"
            )
        if gui is not None:
            # 在 GUI 中记录日志事件
            # Record log events in the GUI
            gui.log_event(log_data)
            # 刷新 GUI
            # Refresh the GUI
            gui.refresh_GUI()
        # 将日志数据放入队列
        # Put the log data into the queue
        log_queue.put(log_data)


class ConfigManager:
    def __init__(self, config_file="config.ini"):
        """
        初始化配置管理器
        Initialize the configuration manager
        """
        # 创建配置解析器对象
        # Create a configuration parser object
        self.config = configparser.ConfigParser()
        # 配置文件路径
        # Configuration file path
        self.config_file = config_file
        if not os.path.exists(self.config_file):
            # 如果配置文件不存在，创建新的配置文件
            # If the configuration file does not exist, create a new configuration file
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
            # 如果配置文件存在，读取配置文件
            # If the configuration file exists, read the configuration file
            self.config.read(self.config_file)

    def get(self, section, option):
        """
        获取配置项的值
        Get the value of the configuration item
        """
        try:
            # 记录日志事件
            # Record log events
            log_event("Server-Setting Service", "successfully", f"{section}>{option}")
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            # 记录警告日志事件
            # Record warning log events
            log_event("Server-Setting Service", "warning", f"{section}>{option}")
            return None

    def get_with_default(self, section, option, default=None):
        """
        获取配置项的值，如果不存在则返回默认值
        Get the value of the configuration item, if it does not exist, return the default value
        """
        try:
            # 记录日志事件
            # Record log events
            log_event("Server-Setting Service", "successfully", f"{section}>{option}")
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            # 记录警告日志事件
            # Record warning log events
            log_event("Server-Setting Service", "warning", f"{section}>{option}")
            return default

    def set(self, section, option, value):
        """
        设置配置项的值
        Set the value of the configuration item
        """
        if not self.config.has_section(section):
            # 如果配置文件中不存在该节，添加该节
            # If the section does not exist in the configuration file, add the section
            self.config.add_section(section)
        # 记录日志事件
        # Record log events
        log_event(
            "Server-Setting Service",
            "successfully",
            f"write {section}>{option} = {value}",
        )
        # 设置配置项的值
        # Set the value of the configuration item
        self.config.set(section, option, value)
        with open(self.config_file, "w") as configfile:
            # 将配置写入文件
            # Write the configuration to the file
            self.config.write(configfile)

    def remove_option(self, section, option):
        """
        移除配置项
        Remove the configuration item
        """
        if self.config.has_section(section) and self.config.has_option(section, option):
            # 如果配置文件中存在该节和该选项，移除该选项
            # If the section and the option exist in the configuration file, remove the option
            self.config.remove_option(section, option)
            # 记录日志事件
            # Record log events
            log_event(
                "Server-Setting Service", "successfully", f"del {section}>{option} "
            )
            with open(self.config_file, "w") as configfile:
                # 将配置写入文件
                # Write the configuration to the file
                self.config.write(configfile)


# 创建配置管理器实例
# Create an instance of the configuration manager
config_manager = ConfigManager()
# 创建控制台对象
# Create a console object
console = Console()
# 创建 Flask 应用实例
# Create a Flask application instance
app = Flask(
    __name__,
    static_url_path="/",
    static_folder="./flask-dist",
    template_folder="./flask-dist",
)

# 配置 Flask-SocketIO 允许跨域
# Configure Flask-SocketIO to allow cross-origin requests
socketios = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_interval=2,
    ping_timeout=60,
)


def delete_files_in_folder(folder_path="./flask-dist/UPLOAD", filename=None):
    """
    删除指定文件夹下的所有文件或指定文件
    Delete all files or specified files in the specified folder

    Args:
      folder_path: 要删除文件的文件夹路径
      folder_path: The path of the folder where the files are to be deleted
      filename: 要删除的文件名（可选）
      filename: The name of the file to be deleted (optional)
    """
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # 构建文件路径
            # Build the file path
            file_path = os.path.join(root, file)
            if (
                filename and file != filename
            ):  # 如果指定了文件名，且当前文件不是指定的文件，则跳过
                continue
            try:
                # 删除文件
                # Delete the file
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            except OSError as e:
                print(f"Error deleting file {file_path}: {e}")


def blacklist_operations(command):
    """
    处理黑名单操作命令
    Handle blacklist operation commands
    """
    if "--help" in command:
        return jsonify(
            "Available parameters are: --help to display available parameters, --add to temporarily add a blacklist command to the backlist list, --remove to temporarily remove a command from the blacklist, --show to display the blacklist instructions (by default, no parameters also means displaying the blacklist instructions)."
        )
    if "--add" in command:
        # 将命令添加到黑名单
        # Add the command to the blacklist
        command_blacklist.append(command.split("--add")[1].strip())
        # 记录日志事件
        # Record log events
        log_event("Server-SQL blacklist", "successfully", f"add {command}")
        return jsonify(
            f"Successfully added '{command.split('--add')[1].strip()}' to the blacklist."
        )
    if "--remove" in command:
        if command.split("--remove")[1].strip() in command_blacklist:
            # 从黑名单中移除命令
            # Remove the command from the blacklist
            command_blacklist.remove(command.split("--remove")[1].strip())
            # 记录日志事件
            # Record log events
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
# Function to execute SQL commands
def execute_sql(command):
    """
    执行 SQL 命令
    Execute SQL commands
    """
    for keyword in command_blacklist:
        if keyword in command.lower():
            # 记录警告日志事件
            # Record warning log events
            log_event(
                "Server-SQL blacklist", "warning", f"Can`t run {command} with SQL"
            )
            return jsonify(f"Commands containing '{keyword}' are prohibited.")

    # Match commands and parameters
    for cmd, (func, params_desc) in sql_command_map.items():
        if command.startswith(cmd):
            # 获取参数部分
            # Get the parameter part
            args = command[len(cmd) :].strip()
            if params_desc == "none" and args:
                # 记录警告日志事件
                # Record warning log events
                log_event(
                    "Server-SQL service", "warning", f"Unacceptable parameter for {cmd}"
                )
                return jsonify(f"Command {cmd} does not accept parameters.")
            try:
                if params_desc != "none":
                    # 记录日志事件
                    # Record log events
                    log_event("Server-SQL service", "successfully")
                    # 执行函数
                    # Execute the function
                    result = func(database_file, args)
                else:
                    # 记录日志事件
                    # Record log events
                    log_event("Server-SQL service", "successfully")
                    # 执行函数
                    # Execute the function
                    result = func(database_file)
                return jsonify(result)
            except Exception as e:
                # 记录错误日志事件
                # Record error log events
                log_event("SQL service", "error", str(e))
                return jsonify(f"Command execution failed: {str(e)}")

    return jsonify(execute_custom_sql(database_file, command))


@app.route("/")
def mainPage():
    """
    主页面路由
    Main page route
    """
    return render_template("index.html")


@app.route(f'/ {API["isHTTPS"]}')
def isHTTPS():
    """
    判断是否使用 HTTPS
    Determine whether to use HTTPS
    """
    return jsonify(port == 443), 200


@app.route(f'/{API["clear"]}')
def clear_files():
    """
    清除文件路由
    Clear files route
    """
    # 从请求参数中获取文件名
    # Get the file name from the request parameters
    filename = request.args.get("filename")
    # 删除指定文件或所有文件
    # Delete the specified file or all files
    delete_files_in_folder(filename=filename)
    return jsonify("Delete"), 200


@app.route(f'/{API["getpicture"]}', methods=["GET"])
def getpic():
    """
    获取图片路由
    Get picture route
    """
    try:
        # 从请求参数中获取文件名
        # Get the file name from the request parameters
        filename = request.args.get("name")
        if not filename:
            # 记录警告日志事件
            # Record warning log events
            log_event(
                "Server-File Service", "warning", f"FileName:{filename} was Invalid"
            )
            return jsonify({"error": "No filename provided"}), 400

        # 确保文件存在
        # Ensure the file exists
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            # 记录错误日志事件
            # Record error log events
            log_event(
                "Server-File Service",
                "error",
                f"The file {file_path} you are looking for does not exist",
            )
            return jsonify({"error": "File does not exist"}), 404

        # 确保 Flask 应用有权限读取文件
        # Ensure that the Flask application has permission to read the file
        if not os.access(file_path, os.R_OK):
            # 记录错误日志事件
            # Record error log events
            log_event(
                "Server-File Service",
                "error",
                f"File {file_path} read permission denied",
            )
            return jsonify({"error": "File is not readable"}), 403

        # 返回图片文件
        # Return the picture file
        log_event("Server-File Service", "successfully", "successfully")
        return send_from_directory(UPLOAD_FOLDER, filename)

    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event(
            "Server-File Service", "error", f"An unhandled exception occurred: {str(e)}"
        )
        return jsonify({"error": "Internal server error"}), 500

def process_file(uuid_file, task_uuid):
    """
    处理文件任务
    Process file tasks
    """
    try:
        # 更新任务状态为 processing
        # Update the task status to processing
        jobs_status[task_uuid] = "processing"
        # 调用 getNum.New_auto_run 处理文件
        # Call getNum.New_auto_run to process the file
        text = getNum.New_auto_run(uuid_file)
        # 记录日志事件
        # Record log events
        log_event("Server-OCR Service", "successfully", f"Task {task_uuid} processing result: {text}")
        # 插入识别记录到数据库
        # Insert recognition records into the database
        insert_recognition_record(db_file=database_file, mold_number=text)
        # 更新任务状态为 completed
        # Update the task status to completed
        jobs_status[task_uuid] = {"status":"completed","text":text}
        return text
    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event("Server-OCR Service", "error", f"Task {task_uuid} processing failed: {str(e)}")
        jobs_status[task_uuid] = {"status":"error","text":f"{str(e)}"}
        return str(e)

@app.route(f'{API["start"]}', methods=["GET"])
def start():
    """
    提交任务路由
    Submit task route
    """
    try:
        # 从请求参数中获取客户端 UUID
        # Get the client UUID from the request parameters
        client_uuid = request.args.get("uuid")
        if not client_uuid:
            return jsonify({"info": "Invalid Client ID"}), 403

        # 构建文件路径
        # Build the file path
        uuid_file = os.path.join(UPLOAD_FOLDER, client_uuid)
        if not os.path.exists(uuid_file):
            return jsonify({"info": "The upload file for this client was not found."}), 404

        if task_queue.full():
            return jsonify({"info": "任务队列已满，请稍后重试"}), 429

        # 生成唯一任务 ID
        # Generate a unique task ID
        task_uuid = str(uuid.uuid4())

        # 记录任务
        # Record the task
        if client_uuid not in jobs:
            jobs[client_uuid] = []
        jobs[client_uuid].append(task_uuid)
        jobs_status[task_uuid] = "waiting"

        # 提交任务
        # Submit the task
        future = executor.submit(process_file, uuid_file, task_uuid)

        return jsonify({"info": "Task has been submitted", "task_uuid": task_uuid, "client_uuid": client_uuid}), 200

    except Exception as e:
        return jsonify({"info": str(e)}), 500


@app.route('/status', methods=["GET"])
def status():
    """
    查询任务状态路由
    Query task status route
    """
    # 从请求参数中获取客户端 UUID
    # Get the client UUID from the request parameters
    client_uuid = request.args.get("uuid")
    # 从请求参数中获取任务 UUID
    # Get the task UUID from the request parameters
    task_uuid = request.args.get("task")

    if task_uuid:  # 查询单个任务
        if task_uuid not in jobs_status:
            return jsonify({"task_uuid": task_uuid, "status": "UUID not found"}), 404
        return jsonify({"task_uuid": task_uuid, "status": jobs_status[task_uuid]}), 200

    if client_uuid:  # 查询设备的所有任务
        if client_uuid not in jobs:
            return jsonify({"client_uuid": client_uuid, "tasks": []}), 200

        # 构建任务状态列表
        # Build the task status list
        task_status_list = [
            {"task_uuid": task_uuid, "status": jobs_status.get(task_uuid, "unknown")}
            for task_uuid in jobs[client_uuid]
        ]
        return jsonify({"client_uuid": client_uuid, "tasks": task_status_list}), 200

    return jsonify({"info": "Missing query parameters"}), 400

@app.route(f'/{API["upload"]}', methods=["POST"])
def upload_file():
    """
    文件上传路由
    File upload route
    """
    try:
        # 从请求参数中获取客户端 UUID
        # Get the client UUID from the request parameters
        client_uuid = request.args.get("uuid")
        if not client_uuid or client_uuid not in clients:
            return jsonify({"error": "Invalid Client ID"}), 403

        # 获取请求中的文件
        # Get the files in the request
        files = request.files
        for file in files:
            if file and files[file].filename != "":
                # 确保文件名安全
                # Ensure the file name is safe
                filename = secure_filename(client_uuid)
                # 构建文件保存路径
                # Build the file save path
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                print(f"Saving file to: {file_path}")  # 调试信息
                # 保存文件
                # Save the file
                files[file].save(file_path)

        # 记录日志事件
        # Record log events
        log_event(
            "Server-Upload Service", "successfully", f"Client {client_uuid} Upload File"
        )
        return jsonify({"message": f"The file has been saved as {filename}"}),200

    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event("Server-Upload Service", "error", f"File acceptance failed:{e}")
        print(f"Error: {e}")  # 打印异常信息
        return jsonify({"error": str(e)}), 500


@app.route(f'/{API["test"]}')
def test():
    """
    测试路由
    Test route
    """
    # 记录日志事件
    # Record log events
    log_event("Server-Communication Detection Service", "successfully")
    return jsonify("You already connect the server now!")


@app.route(f'/{API["info"]}')
def return_info():
    """
    返回文件信息路由
    Return file information route
    """
    # 文件数量
    # Number of files
    file_num = 0
    # 文件列表
    # File list
    file_list = []
    for fn in os.listdir("./flask-dist/UPLOAD"):  # fn 表示的是文件名
        # 文件信息列表
        # File information list
        file_name = []
        # 构建文件 URL
        # Build the file URL
        url = "https" if use_https else "http" + "://{host}:{port}/getpicture?name={fn}"
        # 获取文件大小
        # Get the file size
        fsize = (
            str(round(os.path.getsize("./flask-dist/UPLOAD/" + fn) / 1024 / 1024, 2))
            + "MiB"
        )
        # 文件数量加 1
        # Increase the number of files by 1
        file_num = file_num + 1
        file_name.append(url)
        file_name.append(fn)
        file_name.append(fsize)
        file_list.append(file_name)
    # 记录日志事件
    # Record log events
    log_event("Server-File Service", "successfully")
    return jsonify({"file_count": file_num, "file_list": file_list, "API": API}), 200


@app.errorhandler(404)
def page404(e):
    """
    404 错误处理路由
    404 error handling route
    """
    return render_template("/error_page/404.html"), 404


def print_info(host, port, elseinfo=""):
    """
    打印服务器信息
    Print server information
    """
    # 清屏
    # Clear the screen
    os.system("cls" if os.name.lower() == "nt" else "clear")
    if port == 443:
        print(f"Server will running at https://{host}/")
        if debug == "false":
            # 打开浏览器访问服务器
            # Open the browser to access the server
            webbrowser.open(f"https://{host}/")
    else:
        print(f"Server will running at http://{host}:{port}")
        if debug == "false":
            # 打开浏览器访问服务器
            # Open the browser to access the server
            webbrowser.open(f"http://{host}:{port}")
    print(elseinfo)


# 获取日志 API
# Get log API
@app.route("/getlogs", methods=["GET"])
def get_logs():
    """
    获取日志路由
    Get log route
    """
    try:
        if logSwitch.lower() == "true":
            # 日志列表
            # Log list
            logs = []
            with codecs.open("server.log", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    try:
                        # 解析日志数据
                        # Parse log data
                        data = json.loads(line)
                        logs.append(data)
                    except json.JSONDecodeError as e:
                        # 记录解析失败的行和错误信息
                        # Record the line that failed to parse and the error information
                        log_event(
                            "Server-log parsing error",
                            "error",
                            f"Failed to parse line: '{line}', Error: {e}",
                        )
                        continue

            # 使用 json.dumps 来确保返回 JSON 数据时不转义中文
            # Use json.dumps to ensure that Chinese characters are not escaped when returning JSON data
            response_data = json.dumps(logs, ensure_ascii=False)
            return Response(response_data, mimetype="application/json; charset=utf-8")
        # 记录警告日志事件
        # Record warning log events
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
        # 记录错误日志事件
        # Record error log events
        log_event("SERVER CANNOT READ LOGS", "error", e)


def get_ssl_files_paths(ssh_path, key_ext=".key", crt_ext=".crt"):
    """
    从指定文件夹中查找并返回扩展名为.key和.crt的文件的完整路径。
    Find and return the full paths of files with extensions .key and .crt from the specified folder.

    Args:
        ssh_path (str): 需要搜索的文件夹路径。
        ssh_path (str): The path of the folder to be searched.
        key_ext (str, optional): .key文件扩展名。默认为'.key'。
        key_ext (str, optional): .key file extension. Default is '.key'.
        crt_ext (str, optional): .crt文件扩展名。默认为'.crt'。
        crt_ext (str, optional): .crt file extension. Default is '.crt'.

    Returns:
        tuple: 包含.key文件和.crt文件完整路径的元组。
        tuple: A tuple containing the full paths of the .key file and the .crt file.

    Raises:
        FileNotFoundError: 如果未找到指定扩展名的文件。
        FileNotFoundError: If no files with the specified extensions are found.
    """

    # 确保ssh_path是绝对路径
    # Ensure that ssh_path is an absolute path
    ssh_path = os.path.abspath(ssh_path)

    # 查找所有符合扩展名的文件
    # Find all files that match the extension
    key_files = glob.glob(os.path.join(ssh_path, f"*{key_ext}"))
    crt_files = glob.glob(os.path.join(ssh_path, f"*{crt_ext}"))

    # 如果找到多个文件，这里可以加入额外的逻辑来选择具体的文件
    # If multiple files are found, additional logic can be added here to select specific files
    key_file_path = key_files[0] if key_files else ""
    crt_file_path = crt_files[0] if crt_files else ""

    return key_file_path, crt_file_path


@app.route("/getdatabase")
def get_database():
    """
    获取数据库数据路由
    Get database data route
    """
    # 查询所有识别记录
    # Query all recognition records
    recognition_record_results = query_all_recognition_record(database_file)
    return jsonify({"result": recognition_record_results}), 200


@app.route("/command", methods=["GET"])
def run_command():
    """
    运行命令路由
    Run command route
    """
    global mode
    # 从请求参数中获取命令
    # Get the command from the request parameters
    command = request.args.get("command")
    try:
        if mode == "sql":
            if command.lower() == "exit":
                # 退出 SQL 模式
                # Exit SQL mode
                mode = "normal"
                return jsonify("Exit SQLite")
            # 执行 SQL 命令
            # Execute SQL commands
            result = execute_sql(command)
            return result
        else:
            if command.lower().startswith("help"):
                return jsonify(
                    "Available commands: help (display help information), blacklist (perform blacklist-related operations, can include parameters like --help, etc.), sql (enter standalone SQL execution mode, type 'exit' to return to normal mode)"
                )
            if command.lower().startswith("blacklist"):
                # 处理黑名单操作命令
                # Handle blacklist operation commands
                return blacklist_operations(command)
            if "sql" in command.lower():
                # 进入 SQL 模式
                # Enter SQL mode
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
        # 记录错误日志事件
        # Record error log events
        log_event("Server-SERVER CANNOT RUN COMMAND", "warning", e)
        return jsonify(f"An error occurred: {str(e)}")

@app.route("/adduuid",methods=['GET'])
def add_uuid():
    """
    添加 UUID 路由
    Add UUID route
    """
    # 从请求参数中获取 UUID
    # Get the UUID from the request parameters
    uuid=request.args.get('uuid')
    try:
        with clients_lock:
            if uuid not in clients:
                # 记录客户端 UUID 和对应的 API ID
                # Record the client UUID and the corresponding API ID
                clients[uuid]="API-"+uuid
                # 将新设备事件放入 GUI 队列
                # Put the new device event into the GUI queue
                gui.queue.put({"event": "New device", "UUID": uuid, "aID": "API-"+uuid})
            else:
                pass
            return jsonify({"result": clients[uuid]}), 200
    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event('Server-SERVER CANNOT REGISTER', 'error',e)

@app.route("/removeuuid",methods=['GET'])
def remove_uuid():
    """
    移除 UUID 路由
    Remove UUID route
    """
    # 从请求参数中获取 UUID
    # Get the UUID from the request parameters
    uuid=request.args.get('uuid')
    try:
        with clients_lock:
            # 从客户端列表中移除 UUID
            # Remove the UUID from the client list
            del clients[uuid]
        # 记录日志事件
        # Record log events
        log_event(f"Server-Client {uuid} disconnected", 'info')
    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event('Server-SERVER CANNOT Remove UUID', 'error',e)
    return jsonify({"result": clients[uuid]}), 200

# 监听客户端注册事件（传递 UUID）
# Listen for client registration events (pass UUID)
@socketios.on("register")
def handle_register(data):
    """
    处理客户端注册事件
    Handle client registration events
    """
    try:
        with clients_lock:
            # 获取客户端 UUID
            # Get the client UUID
            client_uuid = data["uuid"]
            if client_uuid not in clients:
                # 记录客户端 UUID 和对应的 socket ID
                # Record the client UUID and the corresponding socket ID
                clients[client_uuid] = request.sid
                # 将新设备事件放入 GUI 队列
                # Put the new device event into the GUI queue
                gui.queue.put({"event": "New device", "UUID": data['uuid'], "aID": request.sid})
                # 发送注册成功消息给客户端
                # Send a registration success message to the client
                send_message_to_client('Client registered successfully', client_uuid)
            else:
                pass
    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event('Server-SERVER CANNOT REGISTER', 'error', e)


@socketios.on("disconnect")
def handle_disconnect():
    """
    处理客户端断开连接事件
    Handle client disconnection events
    """
    uuid = None
    # 查找断开连接的客户端的 uuid，并将其从 clients 中移除
    # Find the uuid of the disconnected client and remove it from clients
    for key, value in clients.items():
        if value == request.sid:
            uuid = key
            break
    if uuid:
        # 删除该客户端的连接信息
        # Delete the connection information of the client
        del clients[uuid]
    # 记录日志事件
    # Record log events
    log_event(f"Server-Client {uuid} disconnected",'info')


# 发送消息到指定客户端
# Send a message to the specified client
def send_message_to_client(message, client_uuid=None):
    """
    发送消息到指定客户端
    Send a message to the specified client
    """
    try:
        if (
            isinstance(client_uuid, str) and len(client_uuid) > 0
        ):  # Ensure UUID is a string
            if client_uuid in clients:
                # 获取客户端的 socket ID
                # Get the socket ID of the client
                sid = clients[client_uuid]
                # 发送消息到客户端
                # Send a message to the client
                socketios.emit("new_message", {"message": message}, to=sid)
                print(f"Message sent to client {client_uuid}")
            else:
                print(f"Client {client_uuid} not found")
        elif client_uuid is None:  # Broadcast message to all online clients
            for uuid, sid in clients.items():
                # 广播消息到所有在线客户端
                # Broadcast the message to all online clients
                socketios.emit("new_message", {"message": message}, to=sid)
            print(f"Message broadcasted to {len(clients)} clients")
        else:
            pass
    except Exception as e:
        # 记录错误日志事件
        # Record error log events
        log_event("Server-SERVER SEND MESSAGE FAILED", "error", str(e))
        raise


def init():
    """
    初始化服务器
    Initialize the server
    """
    # Retrieve user configuration file information
    global host, port, UPLOAD_FOLDER, API, debug, logSwitch, gui, use_https
    # 记录日志事件
    # Record log events
    log_event("Server-Configuration Reading Service", "successfully", first_log=True)

    # 检查并创建数据库
    # Check and create the database
    check_and_create_database(database_file)

    # 从配置文件中获取服务器主机地址
    # Get the server host address from the configuration file
    host = config_manager.get_with_default("Settings", "host", "127.0.0.1")
    # 从配置文件中获取日志开关状态
    # Get the log switch status from the configuration file
    logSwitch = config_manager.get_with_default("Settings", "logSwitch", "true")
    # 从配置文件中获取服务器端口号
    # Get the server port number from the configuration file
    port = config_manager.get_with_default("Settings", "port", "5000")
    # 从配置文件中获取调试模式开关状态
    # Get the debug mode switch status from the configuration file
    debug = config_manager.get_with_default("Settings", "debug", "false")

    # 从配置文件中获取是否使用 HTTPS 的设置
    # Get the setting of whether to use HTTPS from the configuration file
    use_https = (
        not config_manager.get_with_default("SSH_Service", "use_https", "false").lower()
        == "false"
    )
    # 获取 SSL 证书和密钥文件路径
    # Get the paths of the SSL certificate and key files
    ssh_key, ssh_crt = get_ssl_files_paths(
        config_manager.get_with_default("SSH_Service", "ssh_path", "./CRT")
    )

    if config_manager.get_with_default("API_Service", "USE_OPTIONS", "false") == "true":
        # 更新 API 配置
        # Update API configuration
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
        # 记录警告日志事件
        # Record warning log events
        log_event(
            "Server-Configuration Reading Service",
            "warning",
            "API configuration has changed, please update the front-end accordingly",
        )

    # 定义文件上传目录
    # Define the file upload directory
    UPLOAD_FOLDER = "flask-dist/UPLOAD"
    if not os.path.exists(UPLOAD_FOLDER):
        # 如果上传目录不存在，创建该目录
        # If the upload directory does not exist, create the directory
        os.makedirs(UPLOAD_FOLDER)

    # 删除上传目录下的所有文件
    # Delete all files in the upload directory
    delete_files_in_folder()

    if ssh_key != "" and ssh_crt != "":
        if use_https:
            # 记录日志事件
            # Record log events
            log_event(
                "Server-Configuration Reading Service",
                "successfully",
                "HTTPS process started!",
            )
        else:
            # 记录日志事件
            # Record log events
            log_event(
                "Server-Configuration Reading Service",
                "successfully",
                "It looks like you support HTTPS, you can enable it anytime!",
            )
    else:
        # 记录日志事件
        # Record log events
        log_event(
            "Server-Configuration Reading Service",
            "successfully",
            "Server started successfully!",
        )

    # 记录日志事件
    # Record log events
    log_event(
        "Server-SERVER START SUCCESS", "successfully", "Server started successfully"
    )
    print("SERVER START SUCCESS")

    # 配置 Flask 允许跨域
    # Configure Flask to allow cross-origin requests
    CORS(app)

    if use_https:
        # 构建 SSL 上下文
        # Build the SSL context
        context = (f"{ssh_crt}", f"{ssh_key}")
        # 启动 SocketIO 服务器，使用 HTTPS
        # Start the SocketIO server, use HTTPS
        socketios.run(
            debug=debug == "true",
            host=host,
            port=443,
            app=app,
            allow_unsafe_werkzeug=True,
            ssl_context=context,
        )
    else:
        # 启动 SocketIO 服务器，使用 HTTP
        # Start the SocketIO server, use HTTP
        socketios.run(
            debug=debug == "true",
            host=host,
            port=int(port),
            app=app,
            allow_unsafe_werkzeug=True,
        )


def run_tui():
    """
    启动 GUI 界面
    Start the GUI interface
    """
    global gui
    # 从配置文件中获取服务器主机地址，如果未找到则使用默认值 127.0.0.1
    # Get the server host address from the configuration file, if not found, use the default value 127.0.0.1
    host = config_manager.get_with_default("Settings", "host", "127.0.0.1")
    # 从配置文件中获取日志开关状态，如果未找到则使用默认值 true
    # Get the log switch status from the configuration file, if not found, use the default value true
    logSwitch = config_manager.get_with_default("Settings", "logSwitch", "true")
    # 从配置文件中获取服务器端口号，如果未找到则使用默认值 5000
    # Get the server port number from the configuration file, if not found, use the default value 5000
    port = config_manager.get_with_default("Settings", "port", "5000")
    # 从配置文件中获取是否使用 HTTPS 的设置，如果未找到则使用默认值 false
    # Get the setting of whether to use HTTPS from the configuration file, if not found, use the default value false
    use_https = (
        not config_manager.get_with_default("SSH_Service", "use_https", "false").lower()
        == "false"
    )

    # 创建 GUI 实例
    # Create a GUI instance
    gui = ServerGUI(
        # 根据是否使用 HTTPS 构建服务器的 URL
        # Build the server URL according to whether to use HTTPS
        server_url=f"https://{host}" if use_https else f"http://{host}:{port}",
        # 传递是否使用 HTTPS 的设置给 GUI
        # Pass the setting of whether to use HTTPS to the GUI
        use_https=use_https,
        # 从配置文件中获取 SSH 路径，如果未找到则使用默认值 ./CRT
        # Get the SSH path from the configuration file, if not found, use the default value ./CRT
        ssh_path=config_manager.get_with_default("SSH_Service", "ssh_path", "./CRT"),
        # 从配置文件中获取是否使用高级 API 设置，如果未找到则使用默认值 false
        # Get the setting of whether to use the advanced API from the configuration file, if not found, use the default value false
        AdvanceAPISetting=config_manager.get_with_default(
            "API_Service", "USE_OPTIONS", "false"
        ) == "true",
        # 传递日志开关状态给 GUI
        # Pass the log switch status to the GUI
        logSwitch=logSwitch,
        # 传递获取客户端列表的函数给 GUI
        # Pass the function to get the client list to the GUI
        client_func=get_clients,
    )
    # 设置 GUI 创建完成的事件，通知主线程 GUI 已经成功创建
    # Set the event that the GUI has been created, notify the main thread that the GUI has been successfully created
    gui_created_event.set()

    try:
        # 显示 GUI 界面
        # Display the GUI interface
        gui.showGUI()
    except KeyboardInterrupt:
        # 捕获用户按下 Ctrl+C 中断程序的信号，打印关闭信息
        # Capture the signal that the user presses Ctrl+C to interrupt the program, print the shutdown information
        print("Shutting down...")
    finally:
        # 无论是否发生异常，最后都停止 GUI
        # Stop the GUI anyway, whether an exception occurs or not
        gui.stop()


def get_clients():
    """
    获取当前的 clients 列表
    Get the current clients list
    """
    with clients_lock:
        return dict(clients)


# 主功能处理
# Main function processing
def main(args):
    """
    主函数
    Main function
    """
    # 备份数据库
    # Backup the database
    if args.COPYDATABASE:
        # 源数据库文件路径
        # Source database file path
        source_path = "./db/data.db"
        # 目标数据库文件路径
        # Destination database file path
        destination_path = args.COPYDATABASE[0]
        try:
            if os.path.isdir(destination_path):
                # 如果目标路径是目录，构造目标文件路径
                # If the destination path is a directory, construct the destination file path
                destination_path = os.path.join(
                    destination_path, os.path.basename(source_path)
                )
            # 复制数据库文件
            # Copy the database file
            shutil.copy(source_path, destination_path)
            print(f"File copied successfully to {destination_path}")
        except FileNotFoundError:
            print(f"Source file not found: {source_path}")
        except PermissionError:
            print(f"Permission denied: {destination_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
    # 复制数据库
    # Copy the database
    if args.LOADDATABASE:
        # 源数据库文件路径
        # Source database file path
        source_path = "./db/data.db"
        # 目标数据库文件路径
        # Destination database file path
        destination_path = args.LOADDATABASE[0]
        try:
            if os.path.isdir(source_path):
                print(
                    "You must specify the address of the database file, not the directory containing the database file"
                )
                return 0
            # 复制数据库文件
            # Copy the database file
            shutil.copy(destination_path, source_path)
            print(f"File copied successfully from {destination_path}")
        except FileNotFoundError:
            print(f"Source file not found: {source_path}")
        except PermissionError:
            print(f"Permission denied: {destination_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
    # 切割图片
    # Cut images
    if args.CUTIMAGEFROMDIR:
        # 源图片目录
        # Source image directory
        source_dir = args.CUTIMAGEFROMDIR[0]
        # 保存图片目录
        # Save image directory
        save_dir = (
            args.CUTIMAGEFROMDIR[1]
            if len(args.CUTIMAGEFROMDIR) > 1
            else os.path.join(source_dir, "Save")
        )
        print("Command: CUTIMAGEFROMDIR")
        print(f"Source Directory: {source_dir}")
        print(f"Save Directory: {save_dir}")
        # 调用 getNum.quick_cut_img 切割图片
        # Call getNum.quick_cut_img to cut images
        getNum.quick_cut_img(source_dir, save_dir)

    # 处理图片
    # Process images
    if args.PROCESSIMAGEDIR:
        # 源图片目录
        # Source image directory
        source_dir = args.PROCESSIMAGEDIR[0]
        # 保存图片目录
        # Save image directory
        save_dir = args.PROCESSIMAGEDIR[1] if len(args.PROCESSIMAGEDIR) > 1 else None
        print("Command: PROCESSIMAGEDIR")
        print(f"Source Directory: {source_dir}")
        print(f"Save Directory: {save_dir if save_dir else 'Not specified'}")
        # 调用 getNum.process_image 处理图片
        # Call getNum.process_image to process images
        getNum.process_image(source_dir, save_dir)

    # 启动服务器
    # Start the server
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
            # 创建系统监控线程
            # Create a system monitoring thread
            monitor_system_thread = threading.Thread(
                target=flask_send_sysInfo,
                args=(
                    socketios,
                    get_clients,
                ),
            )
            # 设置为守护线程，主线程退出时自动退出
            # Set it as a daemon thread, it will automatically exit when the main thread exits
            monitor_system_thread.daemon = True
            # 启动监控线程
            # Start the monitoring thread
            monitor_system_thread.start()

            # 创建日志写入线程
            # Create a log writing thread
            writer_thread = threading.Thread(target=log_writer, daemon=True)
            writer_thread.daemon = True
            # 启动日志写入线程
            # Start the log writing thread
            writer_thread.start()

            if not args.nogui:
                # 创建 Flask 服务器线程
                # Create a Flask server thread
                flask_thread = threading.Thread(target=init, daemon=True)
                flask_thread.daemon = True
                # 启动 Flask 服务器线程
                # Start the Flask server thread
                flask_thread.start()
            else:
                # 启动服务器
                # Start the server
                init()
                return 0

            if args.simulate:
                if not args.tui:
                    # 创建 GUI 线程
                    # Create a GUI thread
                    flask_gui = threading.Thread(target=run_tui, daemon=True)
                    flask_gui.start()
                time.sleep(5)
                print("Simulation complete. Exiting...")
                return 0
            # 启动 GUI
            # Start the GUI
            run_tui()

        except Exception as e:
            # 记录错误日志事件
            # Record error log events
            log_event("SERVER STATUS", "error", e)
            print(f"SERVER STATUS error: {e}")
            return 1

    return 0


# 初始化参数解析器
# Initialize the parameter parser
def create_parser():
    """
    创建参数解析器
    Create a parameter parser
    """
    parser = argparse.ArgumentParser(description="CCRS Tool")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simulate the startup process without running the TUI.",
    )
    parser.add_argument(
        "--notui", action="store_true", help="Start server without TUI."
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
    # Parse command line parameters
    parser = create_parser()
    args = parser.parse_args()

    # 调用主函数并传递参数
    # Call the main function and pass the parameters
    exit_code = main(args)

    # 退出程序
    # Exit the program
    sys.exit(exit_code)