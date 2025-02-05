import threading
import queue
import time
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

class ServerGUI:
    def __init__(self, server_url, use_https, ssh_path, AdvanceAPISetting, logSwitch, logs=None):
        self.server_url = server_url
        self.use_https = use_https
        self.ssh_path = ssh_path
        self.AdvanceAPISetting = AdvanceAPISetting
        self.logSwitch = logSwitch
        self.logs = logs or []

        self.clients = []
        self.console = Console()
        self.layout = Layout()

        self.sysinfo=[]

        self.queue = queue.Queue()
        self.running = threading.Event()
        self.running.set()

        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
        )
        self.layout["body"].split_row(
            Layout(name="left", size=40),
            Layout(name="right"),
        )

        self.clients_lock = threading.Lock()
        self.logs_lock = threading.Lock()

    def showGUI(self):
        self.layout["header"].update(Panel(Text("铸造字识别系统", style="bold white", justify='center')))
        self.layout["left"].split_column(
            Layout(name="config", size=10),
            Layout(name="table"),
        )

        self.log_panel = Panel("", title="日志显示区域", border_style="red")
        self.layout["right"].update(self.log_panel)

        with Live(self.layout, refresh_per_second=4, screen=True) as live:
            while self.running.is_set():
                self.process_queue()
                self.refresh_GUI()
                live.refresh()
                time.sleep(0.25)  # 控制刷新频率

    def process_queue(self):
        while not self.queue.empty():
            try:
                message = self.queue.get_nowait()
                if message["event"] == "New device":
                    self.add_client(message["UUID"], message["aID"])
                elif message["event"] == "Log event":
                    self.log_event(message)
            except queue.Empty:
                break

    def refresh_GUI(self):
        config_text = f"""
[b]基本配置[/b]
- 服务器URL: {self.server_url}
- HTTPS 服务: {'[red]关闭[/red]' if not self.use_https else '[green]开启[/green]'}
- SSH 路径: {self.ssh_path}
- 高级API设置: {'[red]关闭[/red]' if not self.AdvanceAPISetting else '[green]开启[/green]'}
- 是否允许前端访问日志: {'[green]启用[/green]' if self.logSwitch else '[red]禁用[/red]'}
"""
        config_panel = Panel(config_text, title="基本配置", border_style="blue")
        self.layout["config"].update(config_panel)

        table1 = Table(title="已注册的设备", title_style="bold cyan")
        table1.add_column("UUID", style="cyan", justify="center")
        table1.add_column("aID", style="magenta", justify="center")
        with self.clients_lock:
            for client in self.clients:
                table1.add_row(client[0], client[1])

        table2 = Table(title="系统信息", title_style="bold cyan")
        table2.add_column("CPU", style="cyan", justify="center")
        table2.add_column("RAM", style="magenta", justify="center")
        with self.clients_lock:
            for client in self.sysinfo:
                table2.add_row(client[0], client[1])

        self.layout["table"].update(Panel(table1, title="信息区域", border_style="green"))

        with self.logs_lock:
            log_text = "\n".join(self.logs[-20:])  # 获取最新的20条日志
        log_panel = Panel(log_text, title="日志显示区域", border_style="red")
        self.layout["right"].update(log_panel)

    def add_client(self, UUID, aID):
        with self.clients_lock:
            self.clients.append([UUID, aID])

    def log_event(self, log_data):
        with self.logs_lock:
            self.logs.append(f"{log_data['timestamp']} - {log_data['event']} - {log_data['result']} - {log_data['remark']}")

    def stop(self):
        self.running.clear()

