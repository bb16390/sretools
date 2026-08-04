import os

from fastapi_amis_admin.amis.components import App, Page
from fastapi_user_auth.admin import AuthAdminSite

from master.core.settings import settings

# fastapi_amis_admin 默认模板引用的是 npm CDN 风格的带版本号路径
# (vue@2.7.14/dist/vue.min.js、history@5.3.0/umd/history.production.min.js)，
# 而本项目 amis_cdn=/static，静态资源目录下没有这些带版本号的目录，
# 导致 vue/history 加载 404，admin 页面白屏。
# 这里改用项目本地模板（已去除包名版本号），路径与 /static 下实际文件一致。
_templates_dir = settings.template_name
App.__default_template_path__ = os.path.join(_templates_dir, "app.html")
Page.__default_template_path__ = os.path.join(_templates_dir, "page.html")


class MyAuthAdminSite(AuthAdminSite):
    """
    自定义的AuthAdminSite，继承自 fastapi_user_auth 的 AuthAdminSite，
    自动注册 UserAuthApp（含登录、注册、用户管理、角色权限等）。
    """
    pass
