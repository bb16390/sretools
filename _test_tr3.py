import sys
sys.path.insert(0, "/workspace")
import os
os.chdir("/workspace")

import master.main as main_mod

print("TR-3 代码修改验证：")
print("1. 检查 build_uvicorn_kwargs 是否存在：", hasattr(main_mod, "build_uvicorn_kwargs"))
print("2. 检查 __main__ 分支逻辑（通过查看 build_uvicorn_kwargs 返回值）：")

from master.core.settings import settings
kwargs = main_mod.build_uvicorn_kwargs(settings)
required_keys = ["host", "port", "reload", "workers", "access_log", "log_config", "loop", "http"]
for k in required_keys:
    val = kwargs[k] if k != "log_config" else "(dict, disable_existing_loggers=%s)" % kwargs["log_config"]["disable_existing_loggers"]
    print(f"   包含键 {k}:", k in kwargs, "-> 值:", val)

print()
print("3. 检查导入是否包含 get_uvicorn_log_config：")
import inspect
source = inspect.getsource(main_mod)
print("   get_uvicorn_log_config 导入存在:", "get_uvicorn_log_config" in source and "from master.core.logging import" in source)

print()
print("4. 运行时测试：手动调用 lifespan startup + uvicorn.access logger 写日志 + 显式 flush")

import asyncio
import logging

async def test():
    async with main_mod.lifespan(main_mod.app):
        print("   lifespan 启动完成（此时应已输出 \"应用启动完成\" 日志）")
        access_logger = logging.getLogger("uvicorn.access")
        access_logger.info('127.0.0.1:12345 - "GET / HTTP/1.1" 307')
        main_mod.logger.info("测试：应用运行中的一条普通日志")
        await asyncio.sleep(1)

asyncio.run(test())

root = logging.getLogger("")
for h in root.handlers:
    if hasattr(h, "close"):
        h.close()

for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    l = logging.getLogger(logger_name)
    for h in l.handlers:
        if hasattr(h, "close"):
            h.close()

print()
print("5. 所有 flush 完成，检查日志文件：")
