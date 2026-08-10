import os

from fastapi_amis_admin.amis.components import App, Grid, Html, Page
from fastapi_amis_admin.utils.translation import i18n as _
from fastapi_user_auth.admin import AuthAdminSite
import fastapi_user_auth.admin as _fua_pkg
import fastapi_user_auth.admin.admin as _fua_admin

from master.core.settings import settings

# fastapi_amis_admin 默认模板引用的是 npm CDN 风格的带版本号路径
# (vue@2.7.14/dist/vue.min.js、history@5.3.0/umd/history.production.min.js)，
# 而本项目 amis_cdn=/static，静态资源目录下没有这些带版本号的目录，
# 导致 vue/history 加载 404，admin 页面白屏。
# 这里改用项目本地模板（已去除包名版本号），路径与 /static 下实际文件一致。
_templates_dir = settings.template_name
App.__default_template_path__ = os.path.join(_templates_dir, "app.html")
Page.__default_template_path__ = os.path.join(_templates_dir, "page.html")


def attach_page_head(page: Page) -> Page:
    """自定义 attach_page_head，将 img 链接替换为 settings.site_icon。

    覆盖 fastapi_user_auth 库中的同名函数，使 UserLoginFormAdmin /
    UserRegFormAdmin 渲染登录/注册页头部时使用项目 settings 自定义的 logo。
    """
    desc = _("Amis is a low-code front-end framework that reduces page development effort and greatly improves efficiency")
    page.body = [
        Html(
            html=f'<div style="display: flex; justify-content: center; align-items: center; margin: 96px 0px 8px;">'
            f'<img src="{settings.site_icon}" alt="logo" style="margin-right: 8px; '
            f'width: 48px;"><span style="font-size: 32px; font-weight: bold;">Amis Admin</span></div>'
            f'<div style="width: 100%; text-align: center; color: rgba(0, 0, 0, 0.45); margin-bottom: 40px;">{desc}</div>'
        ),
        Grid(columns=[{"body": [page.body], "lg": 2, "md": 4, "valign": "middle"}], align="center", valign="middle"),
    ]
    return page


# 替换库中的 attach_page_head，使 UserLoginFormAdmin.get_page 引用的版本
# 使用 settings.site_icon 自定义 img 链接。
_fua_admin.attach_page_head = attach_page_head
_fua_pkg.attach_page_head = attach_page_head


class MyAuthAdminSite(AuthAdminSite):
    """
    自定义的AuthAdminSite，继承自 fastapi_user_auth 的 AuthAdminSite，
    自动注册 UserAuthApp（含登录、注册、用户管理、角色权限等）。
    """
    pass
