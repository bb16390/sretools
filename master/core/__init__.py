from master.libs.fastapi_amis_admin import i18n

from master.core.settings import settings

i18n.set_language(settings.language)
