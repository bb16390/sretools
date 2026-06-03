from fastapi import FastAPI, HTTPException
from typing import Dict, Any, List
import time
import json
import os

# 创建FastAPI应用
app = FastAPI()

# 存储worker信息的内存数据库
workers = {}

# 存储worker配置
worker_config = {
    "log_collect_interval": 5,
    "log_batch_size": 1000,
    "log_queue_size": 10000,
    "metric_collect_interval": 10,
    "metric_batch_size": 500
}

# 密钥配置
SECRET_KEY = "your-secret-key-here"


import hmac
import hashlib

def generate_signature(data: Dict[str, Any], secret_key: str) -> str:
    """
    生成请求签名
    """
    # 确保数据包含时间戳
    if "timestamp" not in data:
        data["timestamp"] = int(time.time())
    
    # 按字典键排序
    sorted_keys = sorted(data.keys())
    # 构建签名字符串
    signature_string = "&".join([f"{key}={data[key]}" for key in sorted_keys])
    # 使用HMAC-SHA256生成签名
    signature = hmac.new(
        secret_key.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_signature(data: Dict[str, Any], signature: str, secret_key: str) -> bool:
    """
    验证请求签名
    """
    # 检查时间戳是否在有效范围内（5分钟）
    if "timestamp" not in data:
        return False
    
    current_time = int(time.time())
    if abs(current_time - data["timestamp"]) > 300:
        return False
    
    # 生成期望的签名
    expected_signature = generate_signature(data, secret_key)
    # 验证签名
    return hmac.compare_digest(expected_signature, signature)


@app.post("/api/worker/register")
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
    
    print(f"Worker registered: {worker_id}")
    
    return {
        "status": "success",
        "message": "Worker registered successfully",
        "worker_id": worker_id,
        "config": worker_config
    }

@app.post("/api/worker/heartbeat")
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

@app.get("/api/worker/config")
def get_config():
    """
    获取worker配置
    """
    return {
        "status": "success",
        "config": worker_config
    }

@app.get("/api/health")
def health_check():
    """
    健康检查
    """
    return {
        "status": "healthy",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5500)
