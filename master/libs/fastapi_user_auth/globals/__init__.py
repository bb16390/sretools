from typing import Type

from libs.fastapi_user_auth.admin import AuthAdminSite
from libs.fastapi_user_auth.auth import Auth
from libs.fastapi_user_auth.auth.models import User
from libs.fastapi_amis_admin import globals as g

site: AuthAdminSite

auth: Auth

# 自定义用户ORM模型
UserModel: Type[User]


def __getattr__(name: str):
    if name == "auth":
        return g.site.auth
    elif name == "UserModel" and not hasattr(g, name):
        return g.site.auth.user_model
    return getattr(g, name)
