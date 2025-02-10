import datetime
import platform
import socket
import psutil
import GPUtil
import time
import requests
import json

ip = ""

def get_system_info():
    """获取系统信息，返回字典格式"""
    system_info = {'info': 'Normal', 'os': {
        'platform': platform.system(),
        'release': platform.release(),
        'version': platform.version()
    }, 'hostname': socket.gethostname()}

    try:
        system_info['external_ip'] = get_ip() if ip == "" else ip
    except Exception as e:
        system_info['external_ip'] = {'error': str(e)}

    # 当前服务器时间 (不需要日期, 格式为 00:00 即可)
    now = datetime.datetime.now()
    system_info['current_time'] = now.strftime("%H:%M:%S")

    # 运行时长
    system_info['uptime'] = get_system_uptime()

    # 内存信息
    mem = psutil.virtual_memory()
    system_info['memory'] = {
        'total': mem.total / (1024 * 1024),  # MB
        'used': mem.used / (1024 * 1024),    # MB
        'available': mem.available / (1024 * 1024),  # MB
        'percent': mem.percent
    }
    swap = psutil.swap_memory()
    system_info['swap'] = {
        'total': swap.total / (1024 * 1024),  # MB
        'used': swap.used / (1024 * 1024),    # MB
        'free': swap.free / (1024 * 1024),  # MB
        'percent': swap.percent
    }

    # 处理器信息
    cpu_count = psutil.cpu_count(logical=False)
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_times = psutil.cpu_times()
    system_info['cpu'] = {
        'count': cpu_count,
        'percent': cpu_percent,
        'times': {
            'user': cpu_times.user,
            'system': cpu_times.system,
            'idle': cpu_times.idle
        }
    }

    # 显卡信息
    try:
        gpus = GPUtil.getGPUs()
        system_info['gpus'] = []
        for gpu in gpus:
            system_info['gpus'].append({
                'id': gpu.id,
                'name': gpu.name,
                'driver': gpu.driver,
                'memory_total': gpu.memoryTotal / 1024,  # GB
                'memory_used': gpu.memoryUsed / 1024,    # GB
                'memory_free': gpu.memoryFree / 1024,  # GB
                'memory_percent': gpu.memoryUtil * 100,
                'temperature': gpu.temperature,
                'load': gpu.load * 100
            })
    except Exception as e:
        system_info['gpus'] = {'error': str(e)}

    # 网络信息
    net_io_counters = psutil.net_io_counters()
    system_info['network'] = {
        'bytes_recv': net_io_counters.bytes_recv,
        'bytes_sent': net_io_counters.bytes_sent,
        'packets_recv': net_io_counters.packets_recv,
        'packets_sent': net_io_counters.packets_sent
    }

    return system_info


def get_ip():
    response = requests.get('https://api.ipify.org')
    return response.text  # 输出响应内容


def get_system_uptime():
    # 计算系统的运行时间（以秒为单位）
    uptime = time.time() - psutil.boot_time()
    # 创建一个 timedelta 对象来表示运行时间
    delta = datetime.timedelta(seconds=uptime)
    # 格式化输出，精确到秒
    return f"{delta.days} days, {delta.seconds // 3600:02d}:{delta.seconds % 3600 // 60:02d}:{delta.seconds % 60:02d}"

def send_sysInfo(socketios, get_clients):
    while True:
        try:
            print("Starting new cycle")
            # 获取系统信息
            clients = get_clients()
            system_info = get_system_info()
            if not system_info:
                print("No system info to send")
                continue

            # 将用户数添加到系统信息中
            system_info['Usercount'] = len(clients)

            # 转换为 JSON 字符串
            system_info_json = json.dumps(system_info)

            print(f"Clients: {clients}")
            print("Sending system info to clients")

            # 发送信息给每个客户端
            for uuid, sid in clients.items():
                try:
                    socketios.emit('sysinfo_update', system_info_json, to=sid)
                except Exception as e:
                    print(f"Error sending to {uuid}: {e}")

            print("Cycle completed, sleeping for 2 seconds")
            time.sleep(2)

        except Exception as e:
            print(f"SEND SYSINFO ERROR: {e}")  # 打印错误日志
            time.sleep(2)  # 等待一段时间后再次尝试
