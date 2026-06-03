from typing import Optional

from fastapi import File, UploadFile, Form as FastAPIForm
from fastapi_amis_admin import admin, amis
from fastapi_amis_admin.admin import AdminApp
from fastapi_amis_admin.amis import PageSchema, Form, InputFile, InputText, Textarea
from fastapi_amis_admin.crud.schema import BaseApiOut
from starlette.requests import Request


class FileUploadAdmin(admin.PageAdmin):
    page_schema = PageSchema(label="文件上传", icon="fa fa-upload")

    async def get_page(self, request: Request) -> amis.Page:
        page = amis.Page(
            title="文件上传页面",
            body=[
                amis.Form(
                    api="/api/file-upload/submit",
                    body=[
                        InputText(
                            name="title",
                            label="标题",
                            required=True,
                            placeholder="请输入标题",
                        ),
                        Textarea(
                            name="description",
                            label="描述",
                            placeholder="请输入描述",
                            rows=3,
                        ),
                        InputFile(
                            name="file",
                            label="上传文件",
                            accept="*",
                            maxSize=10 * 1024 * 1024,
                            maxLength=1,
                            multiple=False,
                        ),
                    ],
                    submitText="提交",
                    enctype="multipart/form-data",
                ),
                amis.Divider(),
                amis.Panel(
                    title="提交结果",
                    body=[
                        amis.Json(
                            data="${responseData}",
                            visibleOn="this.responseData",
                        ),
                    ],
                ),
            ],
        )
        return page


class FileUploadApp(admin.AdminApp):
    page_schema = PageSchema(label="文件上传管理", icon="fa fa-file")

    def __init__(self, app: "AdminApp"):
        super().__init__(app)
        self.register_admin(FileUploadAdmin)