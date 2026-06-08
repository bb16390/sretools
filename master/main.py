from contextlib import asynccontextmanager
import threading

from fastapi import FastAPI as FastAPIBase
from fastapi import applications, File, UploadFile, Form
from fastapi.openapi.docs import (
    get_swagger_ui_html,
)
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from index.admin import NavPageAdmin
from index.file_upload_admin import FileUploadApp
from core.globals import auth, site
import logging
import os
import sys
from logging import FileHandler
from core.logging import AsyncFileHandler
from core.settings import settings
from fastapi_amis_admin.crud.schema import BaseApiOut

# 网关控制
try:
    from gateway.admin import GatewayAdminApp
    from gateway.api import router as gateway_router
    GATEWAY_AVAILABLE = True
except Exception as exc:  # noqa: BLE001
    GATEWAY_AVAILABLE = False
    gateway_router = None  # type: ignore[assignment]
    GatewayAdminApp = None  # type: ignore[assignment,misc]
    import logging as _gw_log
    _gw_log.getLogger(__name__).warning("gateway module not available: %s", exc)

# 添加 gRPC 相关导入
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "grpc"))
try:
    from server import start_grpc_server
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

# 配置日志系统
log_dir = os.path.dirname(settings.log_dir)
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# 创建 FileHandler
file_handler = FileHandler(settings.log_dir, encoding='utf-8')
file_handler.setLevel(getattr(logging, settings.log_level))

# 创建 AsyncFileHandler
async_file_handler = AsyncFileHandler(file_handler)

# 配置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 添加处理器到根日志器
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, settings.log_level))
root_logger.addHandler(async_file_handler)

# 创建应用专用日志器
app_logger = logging.getLogger(__name__)


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
        app_logger.info("管理员权限策略添加完成")
    
    if GRPC_AVAILABLE:
        try:
            grpc_thread = threading.Thread(
                target=lambda: start_grpc_server(port=50051, daemon=True),
                daemon=True
            )
            grpc_thread.start()
            app_logger.info("gRPC 服务已启动，端口: 50051")
        except Exception as e:
            app_logger.error(f"启动 gRPC 服务失败: {e}")
    else:
        app_logger.info("gRPC 服务模块不可用，跳过启动")
    
    app_logger.info("应用启动完成")
    yield
    app_logger.info("优雅停机")


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
if GATEWAY_AVAILABLE:
    site.register_admin(GatewayAdminApp)
site.register_admin(FileUploadApp)

# 挂载后台管理系统
site.mount_app(app)

# 挂载网关 HTTP API
if GATEWAY_AVAILABLE and gateway_router is not None:
    app.include_router(gateway_router)


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
        "main:app",
        host=settings.host,
        port=settings.port,
        access_log=True,
        reload=True,
    )
    server = uvicorn.Server(config)

    server.run()
