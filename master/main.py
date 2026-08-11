"""Master 入口。

无论是从项目根目录运行（如 ``python -m master.main``),
还是直接进入 ``master/`` 目录运行（如 ``python main.py``),
本文件都会把 **项目根目录** 正确加入 ``sys.path``,
避免 ``master/grpc`` 子包名与第三方 ``grpcio`` 库发生名称冲突。
"""

import os
import sys
import logging
import threading
from contextlib import asynccontextmanager

# ---------------------------------------------------------------------------
# 1. 确定项目根目录，并清理 / 重置 sys.path，避免 ``master/grpc`` 与
#    第三方 ``grpcio`` 发生包名冲突
# ---------------------------------------------------------------------------
def _detect_project_root() -> str:
    """向上探测包含 ``pyproject.toml`` 的目录作为项目根。"""
    start = globals().get("__file__") or os.getcwd()
    start = os.path.abspath(start)
    if os.path.isfile(start):
        cur = os.path.dirname(start)
    else:
        cur = start
    for _ in range(5):
        if os.path.isfile(os.path.join(cur, "pyproject.toml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    if os.path.basename(os.getcwd()) == "master":
        return os.path.dirname(os.getcwd())
    return os.getcwd()


PROJECT_ROOT = _detect_project_root()
_MASTER_DIR = os.path.join(PROJECT_ROOT, "master")


def _normalize(p: str) -> str:
    try:
        return os.path.normcase(os.path.realpath(p))
    except OSError:
        return p


_MASTER_DIR_NORM = _normalize(_MASTER_DIR)
sys.path[:] = [
    p for p in sys.path
    if p and _normalize(p) not in (_MASTER_DIR_NORM, _normalize(""))
]

if _normalize(PROJECT_ROOT) not in {_normalize(p) for p in sys.path}:
    sys.path.insert(0, PROJECT_ROOT)

try:
    os.chdir(PROJECT_ROOT)
except OSError:
    pass

# ---------------------------------------------------------------------------
# 2. 导入内部模块（必须放在 sys.path 调整之后）
# ---------------------------------------------------------------------------
from fastapi import FastAPI as FastAPIBase  
from fastapi import applications, File, UploadFile, Form  
from fastapi.openapi.docs import (  
    get_swagger_ui_html,
)
from fastapi.staticfiles import StaticFiles  
from sqlmodel import SQLModel  
from starlette.middleware.cors import CORSMiddleware  
from starlette.responses import RedirectResponse  

from master.index.admin import NavPageAdmin  
from master.index.file_upload_admin import FileUploadApp  
from master.core.globals import auth, site  
from master.core.logging import get_uvicorn_log_config
from master.core.settings import settings  
from fastapi_amis_admin.crud.schema import BaseApiOut  


# 日志logger
logger = logging.getLogger(__name__)


class FastAPI(FastAPIBase):
    def __init__(self, *args, **kwargs) -> None:
        if "swagger_js_url" in kwargs:
            self.swagger_js_url = kwargs.pop("swagger_js_url")
        if "swagger_css_url" in kwargs:
            self.swagger_css_url = kwargs.pop("swagger_css_url")
        if "swagger_favicon_url" in kwargs:
            self.swagger_favicon_url = kwargs.pop("swagger_favicon_url")

        def get_swagger_ui_html_with_local(*args, **kwargs):
            return get_swagger_ui_html(
                *args,
                **kwargs,
                swagger_js_url=self.swagger_js_url,
                swagger_css_url=self.swagger_css_url,
                swagger_favicon_url=self.swagger_favicon_url,
            )

        applications.get_swagger_ui_html = get_swagger_ui_html_with_local
        super(FastAPI, self).__init__(*args, **kwargs)


# 添加启动运行事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    await site.db.async_run_sync(SQLModel.metadata.create_all, is_session=False)
    User = await auth.create_role_user("admin")
    Root = await auth.create_role_user("root")
    await site.router.startup()
    if not auth.enforcer.enforce("u:admin", site.unique_id, "page", "page"):
        await auth.enforcer.add_policy(
            "u:admin", site.unique_id, "page", "page", "allow"
        )
        logger.info("管理员权限策略添加完成")
    
    # 添加 gRPC 相关导入（使用绝对包导入，避免遮蔽第三方 grpcio）
    try:
        from master.grpc.server import start_grpc_server
        grpc_thread = threading.Thread(
            target=lambda: start_grpc_server(port=50051, daemon=True),
            daemon=True
        )
        grpc_thread.start()
        logger.info("gRPC 服务已启动，端口: 50051")
    except ImportError:
        logger.info("gRPC 服务模块不可用，跳过启动")
    except Exception as e:
            logger.error(f"启动 gRPC 服务失败: {e}")
    
    logger.info("应用启动完成")
    yield
    logger.info("优雅停机")


# 创建FastAPI实例
app = FastAPI(
    lifespan=lifespan,
    debug=settings.debug,
    swagger_ui_oauth2_redirect_url="/admin/auth/gettoken",
    swagger_js_url=f"{settings.amis_cdn}/swagger/swagger-ui-bundle.js",
    swagger_css_url=f"{settings.amis_cdn}/swagger/swagger-ui.css",
    swagger_favicon_url=f"{settings.amis_cdn}/favicon_b3b0647.png",
)


# 配置静态文件目录
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

site.register_admin(NavPageAdmin)

site.register_admin(FileUploadApp)

# 挂载后台管理系统
site.mount_app(app)

# 挂载网关 HTTP API
# if GATEWAY_AVAILABLE and gateway_router is not None:
#     app.include_router(gateway_router)

# 挂载 MCP Server（Streamable HTTP 传输）
# 客户端端点: http://<host>:<port>/mcp/mcp
try:
    from master.apps.mcp_server import mcp_http_app
    app.mount("/mcp", mcp_http_app())
    logger.info("MCP Server 已挂载至 /mcp/mcp")
except ImportError:
    logger.info("MCP Server 模块不可用，跳过挂载") 


# 文件上传API
@app.post("/api/file-upload/submit")
async def file_upload_submit(
    title: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(None)
):
    result = {"title": title, "description": description}
    
    if file:
        file_content = await file.read()
        result.update({
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(file_content),
        })
    
    return BaseApiOut(data=result, msg="提交成功")

# 注册首页路由
@app.get("/")
async def index():
    return RedirectResponse(url=site.router_path)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(
        "master.main:app",
        host=settings.host,
        port=settings.port,
        access_log=True,
        reload=True,
        log_config=get_uvicorn_log_config(settings),
    )
    server = uvicorn.Server(config)

    server.run()
