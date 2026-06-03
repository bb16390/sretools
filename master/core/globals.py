from sqlalchemy_database import AsyncDatabase
from core.settings import settings

# 导入Auth相关模块
from fastapi_user_auth.auth import Auth
from fastapi_user_auth.auth.backends.db import DbTokenStore

# 创建异步数据库引擎
async_db = AsyncDatabase.create(
    url=settings.database_url_async,
    session_options={
        "expire_on_commit": False,
    },
)

# 使用`DbTokenStore`创建auth对象，使用默认的User模型
auth = Auth(db=async_db, token_store=DbTokenStore(db=async_db,expire_seconds=60 * 60 * 24 * 3600))

# 然后导入MyAuthAdminSite
from core.auth import MyAuthAdminSite

site = MyAuthAdminSite(settings, engine=async_db)
auth = Auth(db=async_db, token_store=DbTokenStore(db=async_db,expire_seconds=60 * 60 * 24 * 3600))
site.auth = auth


# 创建定时任务调度器`SchedulerAdmin`实例
# scheduler = SchedulerAdmin.bind(site)
