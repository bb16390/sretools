from enum import Enum
from typing import Optional

from pydantic import BaseModel, SecretStr, model_validator
from sqlmodel import Field

from master.libs.fastapi_amis_admin.utils.translation import i18n as _

from .models import BaseUser, EmailMixin, PasswordMixin, UsernameMixin


class BaseTokenData(BaseModel):
    id: int
    username: str


class UserLoginOut(BaseUser):
    """用户登录返回信息"""

    token_type: str = "bearer"
    access_token: Optional[str] = None
    password: Optional[SecretStr] = None


class UserRegIn(UsernameMixin, PasswordMixin, EmailMixin):
    """用户注册"""

    password2: str = Field(title=_("Confirm Password"), max_length=128)

    @model_validator(mode="after")
    def check_passwords_match(self):
        if (
            self.password is not None
            and self.password.get_secret_value() != self.password2
        ):
            raise ValueError("passwords do not match!")
        return self


# 默认保留的用户
class SystemUserEnum(str, Enum):
    ROOT = "root"
    ADMIN = "admin"
    GUEST = "guest"
