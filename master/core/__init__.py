from fastapi_amis_admin import i18n

from .settings import settings

i18n.set_language(settings.language)
