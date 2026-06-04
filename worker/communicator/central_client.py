import time
import threading
import requests
import json
import os
import asyncio
import logging
from typing import List, Dict, Any, Optional

import websockets

from worker.core.settings import settings
from worker.core.auth import generate_signature

logger = logging.getLogger(__name__)


class CentralClient:
    def __init__(self):
        self.central_servers = settings.central_servers
        self.current_server_index = 0
        self.timeout = settings.central_timeout
        self.retry_times = settings.central_retry_times
        
        # 服务器健康状态
        self.server_health = {server: True for server in self.central_servers}
        # 服务器故障时间
        self.server_failure_time = {server: 0 for server in self.central_servers}
        # 健康检查间隔
        self.health_check_interval = 10  # 秒
        # 故障恢复检测间隔
        self.recovery_check_interval = 30  # 秒
        
        # 注册状态
        self.registered = False
        
        # WebSocket相关
        self.ws_connected = False
        self.ws_client = None
        self.ws_reconnect_interval = 5  # 初始重连间隔
        self.ws_max_reconnect_interval = 60  # 最大重连间隔
        self.ws_reconnect_attempts = 0  # 重连尝试次数
        self.ws_message_handlers = {}
        self.ws_last_reconnect_time = 0  # 上次重连时间
        
        # 任务调度器引用（由外部注入）
        self._task_scheduler = None
        
        # 交易日缓存引用（由外部注入）
        self._trade_day_cache = None
        
        # 首次启动注册
        self.register()
        
        # 启动心跳线程
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        self.heartbeat_thread.start()
        
        # 启动健康检查线程
        self.health_check_thread = threading.Thread(target=self.check_server_health, daemon=True)
        self.health_check_thread.start()
        
        # 启动WebSocket连接线程
        self.ws_thread = threading.Thread(target=self._start_websocket, daemon=True)
        self.ws_thread.start()
    
    def send_heartbeat(self):
        """
        发送心跳到中心端
        """
        while True:
            try:
                data = {
                    "worker_id": settings.worker_id,
                    "status": "running",
                    "timestamp": time.time()
                }
                self._send_request("/api/worker/heartbeat", data)
                time.sleep(30)  # 每30秒发送一次心跳
            except Exception as e:
                print(f"Error sending heartbeat: {e}")
                time.sleep(10)
    
    def check_server_health(self):
        """
        检查中心端服务器健康状态
        """
        while True:
            try:
                for server in self.central_servers:
                    if self._check_server_health(server):
                        # 服务器恢复
                        if not self.server_health[server]:
                            self.server_health[server] = True
                            print(f"Server {server} recovered")
                    else:
                        # 服务器故障
                        if self.server_health[server]:
                            self.server_health[server] = False
                            self.server_failure_time[server] = time.time()
                            print(f"Server {server} failed")
                            # 触发服务器切换
                            self._switch_server()
                time.sleep(self.health_check_interval)
            except Exception as e:
                print(f"Error checking server health: {e}")
                time.sleep(5)
    
    def _check_server_health(self, server: str) -> bool:
        """
        检查单个服务器的健康状态
        """
        try:
            url = f"{server}/api/worker/health"
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except Exception:
            return False
    
    def _switch_server(self):
        """
        切换到健康的服务器
        """
        # 找到第一个健康的服务器
        for i, server in enumerate(self.central_servers):
            if self.server_health[server]:
                self.current_server_index = i
                print(f"Switched to server: {server}")
                return
    
    def send_logs(self, logs: List[Dict[str, Any]]):
        """
        发送日志到中心端
        """
        data = {
            "worker_id": settings.worker_id,
            "logs": logs
        }
        return self._send_request("/api/worker/logs", data)
    
    def send_metrics(self, metrics: List[Dict[str, Any]]):
        """
        发送指标到中心端
        """
        data = {
            "worker_id": settings.worker_id,
            "metrics": metrics
        }
        return self._send_request("/api/worker/metrics", data)
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """
        从中心端获取配置，如果失败则使用本地缓存
        """
        try:
            config = self._send_request("/api/worker/config", method="GET")
            if config and "config" in config:
                # 保存配置到本地
                self.save_config(config["config"])
                return config["config"]
            else:
                # 尝试加载本地配置
                return self.load_config()
        except Exception as e:
            print(f"Error getting config from central: {e}")
            # 尝试加载本地配置
            return self.load_config()
    
    def _send_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, method: str = "POST") -> Optional[Dict[str, Any]]:
        """
        发送请求到中心端，支持自动切换服务器
        """
        for i in range(len(self.central_servers)):
            server_url = self.central_servers[self.current_server_index]
            
            # 检查服务器是否健康
            if not self.server_health[server_url]:
                print(f"Skipping unhealthy server: {server_url}")
                # 切换到下一个服务器
                self.current_server_index = (self.current_server_index + 1) % len(self.central_servers)
                continue
            
            url = f"{server_url}{endpoint}"
            
            try:
                if method == "POST" and data:
                    # 为POST请求添加签名
                    signed_data = data.copy()
                    signed_data["signature"] = generate_signature(signed_data)
                    response = requests.post(url, json=signed_data, timeout=self.timeout)
                else:
                    response = requests.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Request failed with status code: {response.status_code}")
            except Exception as e:
                print(f"Error communicating with {server_url}: {e}")
                # 标记服务器为不健康
                self.server_health[server_url] = False
                self.server_failure_time[server_url] = time.time()
            
            # 切换到下一个服务器
            self.current_server_index = (self.current_server_index + 1) % len(self.central_servers)
        
        return None
    
    def get_current_server(self) -> str:
        """
        获取当前使用的中心端服务器
        """
        return self.central_servers[self.current_server_index]
    
    def get_server_health(self) -> Dict[str, bool]:
        """
        获取所有服务器的健康状态
        """
        return self.server_health
    
    def register(self):
        """
        注册worker到中心端
        """
        try:
            data = {
                "worker_id": settings.worker_id,
                "info": {
                    "version": settings.version,
                    "host": settings.host,
                    "port": settings.port,
                    "timestamp": time.time()
                }
            }
            response = self._send_request("/api/worker/register", data)
            if response and response.get("status") == "success":
                self.registered = True
                print(f"Worker registered successfully: {settings.worker_id}")
                # 保存配置
                if "config" in response:
                    self.save_config(response["config"])
            else:
                print("Failed to register worker, will use local config if available")
                # 尝试加载本地配置
                self.load_config()
        except Exception as e:
            print(f"Error registering worker: {e}")
            # 尝试加载本地配置
            self.load_config()

    def register_task_scheduler(self, scheduler):
        """
        注册任务调度器，用于接收和处理来自 Master 的调度指令
        """
        self._task_scheduler = scheduler
        logger.info("TaskScheduler registered successfully")

    def set_trade_day_cache(self, cache):
        """
        设置交易日缓存引用
        """
        self._trade_day_cache = cache

    def save_config(self, config: Dict[str, Any]):
        """
        保存配置到本地
        """
        try:
            # 确保存储目录存在
            os.makedirs(settings.local_storage_path, exist_ok=True)
            config_path = os.path.join(settings.local_storage_path, "worker_config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)
            print("Config saved to local storage")
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_config(self):
        """
        从本地加载配置
        """
        try:
            config_path = os.path.join(settings.local_storage_path, "worker_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                print("Loaded config from local storage")
                return config
            else:
                print("No local config found")
                # 如果没有本地配置，启动报错退出
                raise Exception("No local config found and failed to register with master")
        except Exception as e:
            print(f"Error loading config: {e}")
            raise

    def update_servers(self, servers: List[str]):
        """
        更新中心端服务器列表
        """
        self.central_servers = servers
        # 初始化新的服务器健康状态
        for server in servers:
            if server not in self.server_health:
                self.server_health[server] = True
                self.server_failure_time[server] = 0
        # 清理不再存在的服务器
        servers_to_remove = [server for server in self.server_health if server not in servers]
        for server in servers_to_remove:
            del self.server_health[server]
            del self.server_failure_time[server]
        # 重置当前服务器索引
        self.current_server_index = 0
    
    def _start_websocket(self):
        """
        启动WebSocket连接线程
        """
        while True:
            try:
                asyncio.run(self._connect_websocket())
            except Exception as e:
                print(f"WebSocket thread error: {e}")
            
            # 实现指数退避重连策略
            self.ws_reconnect_attempts += 1
            # 计算重连间隔，指数增长但不超过最大值
            backoff_interval = min(self.ws_reconnect_interval * (2 ** (self.ws_reconnect_attempts - 1)), self.ws_max_reconnect_interval)
            
            print(f"WebSocket reconnect attempt {self.ws_reconnect_attempts}, waiting {backoff_interval} seconds...")
            time.sleep(backoff_interval)
            
            # 重置重连尝试次数（如果已经很久没有重连了）
            if time.time() - self.ws_last_reconnect_time > 300:  # 5分钟
                self.ws_reconnect_attempts = 0
            
            self.ws_last_reconnect_time = time.time()
    
    async def _connect_websocket(self):
        """
        连接到WebSocket服务器
        """
        current_server = self.get_current_server()
        ws_url = current_server.replace("http", "ws") + f"/api/worker/ws/{settings.worker_id}"
        
        print(f"Connecting to WebSocket server: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                self.ws_client = websocket
                self.ws_connected = True
                # 连接成功后重置重连尝试次数
                self.ws_reconnect_attempts = 0
                print(f"WebSocket connected successfully to {ws_url}")
                
                # 注册默认消息处理器
                self.register_message_handler("config_update", self._handle_config_update)
                self.register_message_handler("task_update", self._handle_task_update)
                self.register_message_handler("trade_day_data", self._handle_trade_day_data)
                
                # 持续接收消息
                while True:
                    try:
                        message = await websocket.recv()
                        await self._handle_websocket_message(message)
                    except websockets.ConnectionClosed as e:
                        print(f"WebSocket connection closed: {e}")
                        break
                    except Exception as e:
                        print(f"Error receiving WebSocket message: {e}")
                        # 继续接收下一条消息，不中断连接
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            self.ws_connected = False
            self.ws_client = None
    
    async def _handle_websocket_message(self, message):
        """
        处理接收到的WebSocket消息
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type and message_type in self.ws_message_handlers:
                handler = self.ws_message_handlers[message_type]
                await handler(data)
            else:
                print(f"Unknown message type: {message_type}")
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
    
    async def _handle_config_update(self, data):
        """
        处理配置更新消息
        """
        config = data.get("config")
        if config:
            print(f"Received config update: {config}")
            # 保存配置到本地
            self.save_config(config)
    
    async def _handle_task_update(self, data):
        """
        处理任务更新消息，解析调度指令并转发到 TaskScheduler
        """
        task = data.get("task")
        if not task:
            return

        action = task.get("action")
        config = task.get("config", {})

        logger.info(f"Received task update: action={action}, task={task}")

        if self._task_scheduler is None:
            logger.warning("TaskScheduler not registered, ignoring task update")
            return

        if action == "task_create":
            task_type = task.get("task_type")
            self._task_scheduler.create_task(task_type, config)
        elif action == "task_stop":
            task_id = task.get("task_id")
            self._task_scheduler.stop_task(task_id)
        elif action == "task_pause":
            task_id = task.get("task_id")
            self._task_scheduler.pause_task(task_id)
        elif action == "task_resume":
            task_id = task.get("task_id")
            self._task_scheduler.resume_task(task_id)
        else:
            logger.warning(f"Unknown task action: {action}")
    
    async def _handle_trade_day_data(self, data):
        """
        处理交易日数据消息
        """
        trade_days = data.get("trade_days", [])
        if trade_days:
            from datetime import datetime
            dates = [datetime.strptime(day, "%Y-%m-%d").date() for day in trade_days]
            if self._trade_day_cache:
                self._trade_day_cache.update_trade_days(dates)
    
    def register_message_handler(self, message_type: str, handler):
        """
        注册消息处理器
        """
        self.ws_message_handlers[message_type] = handler
        print(f"Registered message handler for type: {message_type}")
    
    def unregister_message_handler(self, message_type: str):
        """
        取消注册消息处理器
        """
        if message_type in self.ws_message_handlers:
            del self.ws_message_handlers[message_type]
            print(f"Unregistered message handler for type: {message_type}")
    
    async def send_websocket_message(self, message: Dict[str, Any]):
        """
        发送WebSocket消息
        """
        if self.ws_connected and self.ws_client:
            try:
                await self.ws_client.send(json.dumps(message))
                return True
            except Exception as e:
                print(f"Error sending WebSocket message: {e}")
                self.ws_connected = False
                self.ws_client = None
        return False
