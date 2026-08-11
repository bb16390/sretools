import sys
import os
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from fastapi_amis_admin import admin

# 获取master目录的绝对路径
MASTER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 项目根目录 (master 目录的上一级)
PROJECT_ROOT = os.path.dirname(MASTER_DIR)
# 所有日志文件统一存放目录
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")


class Settings(admin.Settings):
    allow_origins: list = ["*"]

    host: str = "0.0.0.0"
    port: int = 5500
    debug: bool = True
    version: str = "0.0.0"
    site_title: str = "SRE Tools"
    site_icon: str = "/static/favicon_b3b0647.png"
    site_url: str = ""
    site_path: str = "/admin"
    # database_url_async: str = (
    #     f"postgresql+asyncpg://itopr:{quote_plus('Ums2015@#')}@10.21.1.12:5432/itopr"
    # )
    database_url_async: str = f"sqlite+aiosqlite:///{Path(MASTER_DIR, 'amisadmin.db').as_posix()}?check_same_thread=False"
    database_url: str = ""
    language: Literal["zh_CN", "en_US"] = "zh_CN"
    # amis_cdn: str = "https://npm.onmicrosoft.cn"
    # amis_pkg: str = "amis@6.3.0"
    amis_cdn: str = "/static"
    amis_pkg: str = "amis"
    amis_theme: Literal["cxd", "antd", "dark", "ang"] = "cxd"
    static_dir: str = os.path.join(MASTER_DIR, "static")

    # ========== uvicorn 运行参数 ==========
    uvicorn_reload: bool = False
    uvicorn_workers: int = 1
    uvicorn_access_log: bool = True

    # ========== 日志配置 ==========
    log_level: str = "DEBUG"
    log_file: str = os.path.join(LOGS_DIR, "master.log")
    error_log_file: str = os.path.join(LOGS_DIR, "master-error.log")
    # 日志格式
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    access_log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    # 日志轮转参数
    log_rotation_when: str = "midnight"
    log_rotation_interval: int = 1
    log_backup_count: int = 30
    log_rotation_encoding: str = "utf-8"

    template_name: str = os.path.join(MASTER_DIR, "templates")
    # 安全配置
    secret_key: str = "your-secret-key-here"
    # 网关控制
    gateway_install_root: str = os.path.join(MASTER_DIR, "data", "gateways", "install")
    gateway_backup_root: str = os.path.join(MASTER_DIR, "data", "gateways", "backup")

    @classmethod
    def valid_database_url_(cls, values):
        # 重写父类校验器:保留 file upload api 默认值设置,
        # 但不注入父类的相对路径默认值,使子类 database_url_async
        # 字段默认值(基于 MASTER_DIR 的绝对路径,Windows 兼容)自然生效。
        file_upload_api = f"post:{values.get('site_path', '')}/file/upload"
        values.setdefault("amis_image_receiver", file_upload_api)
        values.setdefault("amis_file_receiver", file_upload_api)
        return values


settings = Settings()




