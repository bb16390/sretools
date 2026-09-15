from fastapi import FastAPI


def setup(app: FastAPI):

    from . import admin, apis, jobs

    app.include_router(apis.router)
