"""基于 APScheduler 的采集模块。

支持三种采集方式：
- database: 通过 SQL 查询数据库
- http: HTTP 请求采集
- websocket: WebSocket 长连接采集

支持自定义存储目的地：
- database: 写入数据库
- http: HTTP 回调
- file: 写入文件
- kafka: 写入 Kafka
"""

from fastapi import FastAPI


def setup(app: FastAPI):
    # 1. 导入管理应用
    # 2. 注册普通路由
    from . import admin, apis

    app.include_router(apis.router)