from fastapi import APIRouter, HTTPException, Depends
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
import time
import json
import os

from core.settings import settings
from core.security import verify_signature, SECRET_KEY

# 创建worker路由器
router = APIRouter(prefix="/api/worker", tags=["worker"])

# 存储worker信息的内存数据库
workers = {}

# 存储worker WebSocket连接
worker_connections = {}

# Store worker configuration
worker_config = {
    "log_collect_interval": 5,
    "log_batch_size": 1000,
    "log_queue_size": 10000,
    "metric_collect_interval": 10,
    "metric_batch_size": 500,
    "kafka_enabled": False,
    "kafka_brokers": "localhost:9092",
    "kafka_group_id": "log-collector-group",
    "kafka_topics": "logs",
    "kafka_auto_offset_reset": "earliest",
    "kafka_enable_auto_commit": False,
    "kafka_offset_report_interval": 30,
    "kafka_offset_file_path": "kafka_offsets.json"
}

# 存储 worker 任务
worker_tasks = {}

# 存储 Kafka 消费进度
kafka_offsets = {}

class ConnectionManager:
    def __init__(self):
        # 存储活跃的WebSocket连接
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, worker_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[worker_id] = websocket
        print(f"Worker {worker_id} connected via WebSocket")
    
    def disconnect(self, worker_id: str):
        if worker_id in self.active_connections:
            del self.active_connections[worker_id]
            print(f"Worker {worker_id} disconnected from WebSocket")
    
    async def send_personal_message(self, message: Dict[str, Any], worker_id: str):
        if worker_id in self.active_connections:
            try:
                await self.active_connections[worker_id].send_json(message)
                print(f"Sent message to worker {worker_id}: {message}")
            except Exception as e:
                print(f"Error sending message to worker {worker_id}: {e}")
                # 移除失败的连接
                self.disconnect(worker_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        for worker_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to worker {worker_id}: {e}")
                # 移除失败的连接
                self.disconnect(worker_id)

# 创建连接管理器
manager = ConnectionManager()

@router.post("/register")
def register_worker(data: Dict[str, Any]):
    """
    注册worker
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    
    workers[worker_id] = {
        "worker_id": worker_id,
        "status": "online",
        "last_registered": time.time(),
        "last_heartbeat": time.time(),
        "info": data.get("info", {})
    }
    
    return {
        "status": "success",
        "message": "Worker registered successfully",
        "worker_id": worker_id,
        "config": worker_config
    }

@router.post("/heartbeat")
def heartbeat(data: Dict[str, Any]):
    """
    接收worker心跳
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    
    if worker_id not in workers:
        raise HTTPException(status_code=404, detail="Worker not registered")
    
    workers[worker_id]["last_heartbeat"] = time.time()
    workers[worker_id]["status"] = data.get("status", "running")
    
    return {
        "status": "success",
        "message": "Heartbeat received",
        "timestamp": time.time()
    }

@router.get("/config")
def get_config():
    """
    获取worker配置
    """
    return {
        "status": "success",
        "config": worker_config
    }

@router.post("/logs")
def receive_logs(data: Dict[str, Any]):
    """
    接收worker日志
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    logs = data.get("logs", [])
    
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    
    if worker_id not in workers:
        raise HTTPException(status_code=404, detail="Worker not registered")
    
    # 这里可以添加日志处理逻辑
    print(f"Received {len(logs)} logs from worker {worker_id}")
    
    return {
        "status": "success",
        "message": f"Received {len(logs)} logs",
        "timestamp": time.time()
    }

@router.post("/metrics")
def receive_metrics(data: Dict[str, Any]):
    """
    接收worker指标
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    metrics = data.get("metrics", [])
    
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    
    if worker_id not in workers:
        raise HTTPException(status_code=404, detail="Worker not registered")
    
    # 这里可以添加指标处理逻辑
    print(f"Received {len(metrics)} metrics from worker {worker_id}")
    
    return {
        "status": "success",
        "message": f"Received {len(metrics)} metrics",
        "timestamp": time.time()
    }

@router.get("/list")
def list_workers():
    """
    获取所有worker列表
    """
    return {
        "status": "success",
        "workers": list(workers.values())
    }

@router.get("/health")
def health_check():
    """
    健康检查
    """
    return {
        "status": "healthy",
        "timestamp": time.time()
    }

@router.websocket("/ws/{worker_id}")
async def websocket_endpoint(websocket: WebSocket, worker_id: str):
    """
    WebSocket连接端点，用于实时推送消息给worker
    """
    await manager.connect(worker_id, websocket)
    try:
        while True:
            # 接收worker的消息（如果需要）
            data = await websocket.receive_json()
            print(f"Received message from worker {worker_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(worker_id)
    except Exception as e:
        print(f"WebSocket error for worker {worker_id}: {e}")
        manager.disconnect(worker_id)

@router.post("/update-config")
def update_worker_config(data: Dict[str, Any]):
    """
    更新worker配置并推送给指定worker
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    config = data.get("config")
    
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    
    if not config:
        raise HTTPException(status_code=400, detail="config is required")
    
    # 更新配置
    if worker_id == "all":
        # 更新所有worker的配置
        global worker_config
        worker_config.update(config)
    else:
        # 更新指定worker的配置
        if worker_id not in workers:
            raise HTTPException(status_code=404, detail="Worker not registered")
        # 这里可以存储每个worker的独立配置
        pass
    
    # 推送配置更新通知
    import asyncio
    message = {
        "type": "config_update",
        "config": config,
        "timestamp": time.time()
    }
    
    if worker_id == "all":
        asyncio.create_task(manager.broadcast(message))
    else:
        asyncio.create_task(manager.send_personal_message(message, worker_id))
    
    return {
        "status": "success",
        "message": f"Config updated for worker {worker_id}",
        "timestamp": time.time()
    }

@router.post("/update-task")
def update_worker_task(data: Dict[str, Any]):
    """
    更新worker任务并推送给指定worker
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    task = data.get("task")
    
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    
    if not task:
        raise HTTPException(status_code=400, detail="task is required")
    
    # 更新任务
    worker_tasks[worker_id] = task
    
    # 推送任务更新通知
    import asyncio
    message = {
        "type": "task_update",
        "task": task,
        "timestamp": time.time()
    }
    
    asyncio.create_task(manager.send_personal_message(message, worker_id))
    
    return {
        "status": "success",
        "message": f"Task updated for worker {worker_id}",
        "timestamp": time.time()
    }


@router.post("/kafka-offsets")
def report_kafka_offsets(data: Dict[str, Any]):
    """
    接收并存储 Worker 上报的 Kafka 消费进度
    """
    # 验证签名
    signature = data.pop("signature", None)
    if not signature or not verify_signature(data, signature, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    worker_id = data.get("worker_id")
    offsets = data.get("offsets")
    
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    if not offsets:
        raise HTTPException(status_code=400, detail="offsets are required")
    
    # 存储消费进度
    kafka_offsets[worker_id] = {
        "worker_id": worker_id,
        "offsets": offsets,
        "timestamp": time.time()
    }
    
    print(f"Received Kafka offsets from worker {worker_id}: {offsets}")
    
    return {
        "status": "success",
        "message": "Kafka offsets stored successfully",
        "timestamp": time.time()
    }


@router.get("/kafka-offsets/{worker_id}")
def get_kafka_offsets(worker_id: str):
    """
    获取指定 Worker 的 Kafka 消费进度
    """
    if worker_id not in kafka_offsets:
        raise HTTPException(status_code=404, detail="Kafka offsets not found for this worker")
    
    return {
        "status": "success",
        "data": kafka_offsets[worker_id],
        "timestamp": time.time()
    }
