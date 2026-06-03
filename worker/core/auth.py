import hmac
import hashlib
import time
from typing import Dict, Any

from worker.core.settings import settings


def generate_signature(data: Dict[str, Any]) -> str:
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
        settings.secret_key.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_signature(data: Dict[str, Any], signature: str) -> bool:
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
    expected_signature = generate_signature(data)
    # 验证签名
    return hmac.compare_digest(expected_signature, signature)
