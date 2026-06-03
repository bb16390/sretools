import sys
import os
from typing import Literal
from urllib.parse import quote_plus

from fastapi_amis_admin import admin

# 获取master目录的绝对路径
MASTER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    database_url_async: str = f"sqlite:///{os.path.join(MASTER_DIR, 'amisadmin.db')}?check_same_thread=False"
    database_url: str = ""
    language: Literal["zh_CN", "en_US"] = "zh_CN"
    # amis_cdn: str = "https://npm.onmicrosoft.cn"
    # amis_pkg: str = "amis@6.3.0"
    amis_cdn: str = "/static"
    amis_pkg: str = "amis"
    amis_theme: Literal["cxd", "antd", "dark", "ang"] = "cxd"
    static_dir: str = os.path.join(MASTER_DIR, "static")
    # 日志配置
    log_level: str = "DEBUG"
    log_dir: str = os.path.join(MASTER_DIR, "log", "uvicorn.log")
    error_log_dir: str = os.path.join(MASTER_DIR, "log", "uvicorn-error.log")
    template_name: str = os.path.join(MASTER_DIR, "templates")
    # 安全配置
    secret_key: str = "your-secret-key-here"


settings = Settings()




