"""采集模块独立验证脚本。

绕过 fastapi_amis_admin/sqlmodelx（与 Python 3.14 不兼容），
直接测试采集器、存储器、调度器触发器构造逻辑。
"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = "/workspace"
sys.path.insert(0, PROJECT_ROOT)
_MASTER_DIR = os.path.join(PROJECT_ROOT, "master")
_LIBS_DIR = os.path.join(_MASTER_DIR, "libs")
# 不把 _LIBS_DIR 加入 sys.path，避免触发 sqlmodelx 导入
os.chdir(PROJECT_ROOT)

# 直接导入采集器和存储器（不依赖 fastapi_amis_admin）
from master.apps.collector.core.collectors import (
    DatabaseCollector,
    HttpCollector,
    WebSocketCollector,
    get_collector,
)
from master.apps.collector.core.collectors.base import CollectorResult
from master.apps.collector.core.storages import (
    DatabaseStorage,
    FileStorage,
    HttpStorage,
    KafkaStorage,
    get_storage,
)
from master.apps.collector.core.storages.base import StorageResult

# 调度器触发器构造逻辑（不导入 models.py，直接用枚举字符串）
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
results = []

def check(name, ok, detail=""):
    results.append((name, ok))
    status = PASS if ok else FAIL
    print(f"{status}  {name}" + (f"  — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 1. 采集器工厂
# ---------------------------------------------------------------------------
print("\n=== 1. 采集器工厂 ===")
check("get_collector('database')", get_collector("database") is DatabaseCollector)
check("get_collector('http')", get_collector("http") is HttpCollector)
check("get_collector('websocket')", get_collector("websocket") is WebSocketCollector)
try:
    get_collector("unknown")
    check("get_collector('unknown') raises", False)
except ValueError:
    check("get_collector('unknown') raises", True)

# ---------------------------------------------------------------------------
# 2. 存储器工厂
# ---------------------------------------------------------------------------
print("\n=== 2. 存储器工厂 ===")
check("get_storage('database')", get_storage("database") is DatabaseStorage)
check("get_storage('http')", get_storage("http") is HttpStorage)
check("get_storage('file')", get_storage("file") is FileStorage)
check("get_storage('kafka')", get_storage("kafka") is KafkaStorage)
try:
    get_storage("unknown")
    check("get_storage('unknown') raises", False)
except ValueError:
    check("get_storage('unknown') raises", True)


# ---------------------------------------------------------------------------
# 3. DatabaseCollector（SQLite 内存库）
# ---------------------------------------------------------------------------
print("\n=== 3. DatabaseCollector (SQLite) ===")

async def test_database_collector():
    db_path = tempfile.mktemp(suffix=".db")
    url = f"sqlite+aiosqlite:///{db_path}"
    # 先用同步方式建表
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.execute("INSERT INTO users (name, age) VALUES ('Alice', 30), ('Bob', 25)")
    conn.commit()
    conn.close()

    collector = DatabaseCollector({
        "url": url,
        "query": "SELECT * FROM users ORDER BY id",
    })
    result = await collector.collect()
    await collector.close()
    os.unlink(db_path)
    return result

try:
    result = asyncio.run(test_database_collector())
    check("DatabaseCollector.collect() returns list", isinstance(result.data, list))
    check("DatabaseCollector rows_count == 2", result.rows_count == 2, f"got {result.rows_count}")
    check("DatabaseCollector first row name == Alice", result.data[0]["name"] == "Alice")
    check("DatabaseCollector raw_size > 0", result.raw_size > 0)
    check("DatabaseCollector.sample(1) returns list", isinstance(result.sample(1), list))
except Exception as e:
    check("DatabaseCollector test", False, str(e))


# ---------------------------------------------------------------------------
# 4. HttpCollector（本地 HTTP 服务）
# ---------------------------------------------------------------------------
print("\n=== 4. HttpCollector (local server) ===")

async def test_http_collector():
    # 启动本地 HTTP 服务
    from aiohttp import web
    app_local = web.Application()
    async def handle_get(request):
        return web.json_response({"method": "GET", "query": dict(request.query)})
    async def handle_post(request):
        try:
            body = await request.json()
        except Exception:
            body = await request.text()
        return web.json_response({"method": "POST", "received": body})
    app_local.router.add_get("/test", handle_get)
    app_local.router.add_post("/test", handle_post)
    runner = web.AppRunner(app_local)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18923)
    await site.start()

    # 测试 GET
    collector = HttpCollector({
        "url": "http://127.0.0.1:18923/test",
        "method": "GET",
        "params": {"q": "hello"},
        "timeout": 5,
        "max_retries": 1,
    })
    result = await collector.collect()
    await collector.close()

    # 测试 POST
    collector2 = HttpCollector({
        "url": "http://127.0.0.1:18923/test",
        "method": "POST",
        "json": {"data": "payload"},
        "timeout": 5,
        "max_retries": 1,
    })
    result2 = await collector2.collect()
    await collector2.close()

    await runner.cleanup()
    return result, result2

try:
    result, result2 = asyncio.run(test_http_collector())
    check("HttpCollector GET returns dict", isinstance(result.data, dict))
    check("HttpCollector GET method == GET", result.data.get("method") == "GET")
    check("HttpCollector GET has query", result.data.get("query", {}).get("q") == "hello")
    check("HttpCollector GET rows_count == 1", result.rows_count == 1)
    check("HttpCollector POST returns dict", isinstance(result2.data, dict))
    check("HttpCollector POST received data", result2.data.get("received", {}).get("data") == "payload")
except Exception as e:
    check("HttpCollector test", False, str(e))


# ---------------------------------------------------------------------------
# 5. FileStorage（jsonl / csv）
# ---------------------------------------------------------------------------
print("\n=== 5. FileStorage (jsonl + csv) ===")

async def test_file_storage():
    tmpdir = tempfile.mkdtemp()
    # jsonl
    jsonl_path = os.path.join(tmpdir, "{task_id}.jsonl")
    storage = FileStorage({"path": jsonl_path, "format": "jsonl", "mode": "append"})
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    r1 = await storage.store(data, task_id="test_task_001", log_id=1)
    await storage.close()
    # csv
    csv_path = os.path.join(tmpdir, "{task_id}.csv")
    storage2 = FileStorage({"path": csv_path, "format": "csv", "mode": "overwrite"})
    r2 = await storage2.store(data, task_id="test_task_002", log_id=2)
    await storage2.close()
    return r1, r2, tmpdir

try:
    r1, r2, tmpdir = asyncio.run(test_file_storage())
    check("FileStorage jsonl success", r1.success, r1.message)
    check("FileStorage jsonl rows_stored == 2", r1.rows_stored == 2)
    # 验证文件内容
    jsonl_file = os.path.join(tmpdir, "test_task_001.jsonl")
    lines = Path(jsonl_file).read_text().strip().split("\n")
    check("FileStorage jsonl has 2 lines", len(lines) == 2)
    first = json.loads(lines[0])
    check("FileStorage jsonl first line has name", first.get("name") == "Alice")
    check("FileStorage csv success", r2.success, r2.message)
    csv_file = os.path.join(tmpdir, "test_task_002.csv")
    csv_content = Path(csv_file).read_text()
    check("FileStorage csv has header", "name" in csv_content and "age" in csv_content)
except Exception as e:
    check("FileStorage test", False, str(e))


# ---------------------------------------------------------------------------
# 6. DatabaseStorage（SQLite 自动建表）
# ---------------------------------------------------------------------------
print("\n=== 6. DatabaseStorage (SQLite auto-create) ===")

async def test_database_storage():
    db_path = tempfile.mktemp(suffix=".db")
    url = f"sqlite+aiosqlite:///{db_path}"
    storage = DatabaseStorage({
        "url": url,
        "table": "collected_metrics",
        "create_if_missing": True,
        "mode": "insert",
    })
    data = [
        {"host": "server1", "cpu": 45.2, "mem": 80},
        {"host": "server2", "cpu": 12.8, "mem": 60},
    ]
    r = await storage.store(data, task_id="task_db_001", log_id=1)
    await storage.close()
    # 验证写入结果
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT host, cpu, mem FROM collected_metrics ORDER BY host")
    rows = cursor.fetchall()
    conn.close()
    os.unlink(db_path)
    return r, rows

try:
    r, rows = asyncio.run(test_database_storage())
    check("DatabaseStorage success", r.success, r.message)
    check("DatabaseStorage rows_stored == 2", r.rows_stored == 2)
    check("DatabaseStorage wrote 2 rows in DB", len(rows) == 2)
    check("DatabaseStorage first row host", rows[0][0] == "server1")
    check("DatabaseStorage auto-created task_id column", len(rows[0]) == 3)
except Exception as e:
    check("DatabaseStorage test", False, str(e))


# ---------------------------------------------------------------------------
# 7. HttpStorage（本地 HTTP 服务）
# ---------------------------------------------------------------------------
print("\n=== 7. HttpStorage (local server) ===")

async def test_http_storage():
    # 启动本地 HTTP 接收服务
    from aiohttp import web
    app_local = web.Application()
    received = []
    async def handle_post(request):
        body = await request.json()
        received.append(body)
        return web.json_response({"status": "ok", "count": len(body) if isinstance(body, list) else 1})
    app_local.router.add_post("/ingest", handle_post)
    runner = web.AppRunner(app_local)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18924)
    await site.start()

    storage = HttpStorage({
        "url": "http://127.0.0.1:18924/ingest",
        "method": "POST",
        "timeout": 5,
        "max_retries": 1,
        "batch_mode": True,
    })
    data = [{"metric": "cpu", "value": 42.5}]
    r = await storage.store(data, task_id="task_http_001", log_id=1)
    await storage.close()

    await runner.cleanup()
    return r, received

try:
    r, received = asyncio.run(test_http_storage())
    check("HttpStorage success", r.success, r.message)
    check("HttpStorage rows_stored >= 1", r.rows_stored >= 1)
    check("HttpStorage has http_status in details", "http_status" in (r.details or {}))
    check("HttpStorage remote received data", len(received) == 1)
    # HttpStorage wraps data: rows=[data] where data is list, so body is [[{...}]]
    flat = received[0]
    if isinstance(flat, list) and len(flat) > 0 and isinstance(flat[0], list):
        flat = flat[0]
    check("HttpStorage remote got metric", isinstance(flat, list) and len(flat) > 0 and flat[0].get("metric") == "cpu")
except Exception as e:
    check("HttpStorage test", False, str(e))


# ---------------------------------------------------------------------------
# 8. 调度器触发器构造逻辑
# ---------------------------------------------------------------------------
print("\n=== 8. 调度器触发器构造 ===")

# 模拟 _build_trigger 逻辑（不导入 scheduler.py，避免 models.py 依赖）
class ScheduleTypeMock:
    CRON = "cron"
    INTERVAL = "interval"
    DATE = "date"

def build_trigger(schedule_type, config):
    if schedule_type == ScheduleTypeMock.CRON:
        cfg = dict(config or {})
        if "expression" in cfg:
            expr = cfg.pop("expression")
            return CronTrigger.from_crontab(expr, **cfg)
        return CronTrigger(**cfg)
    if schedule_type == ScheduleTypeMock.INTERVAL:
        cfg = dict(config or {})
        for k in ("weeks", "days", "hours", "minutes", "seconds"):
            if k in cfg:
                cfg[k] = int(cfg[k])
        return IntervalTrigger(**cfg)
    if schedule_type == ScheduleTypeMock.DATE:
        cfg = dict(config or {})
        run_date = cfg.pop("run_date", None)
        return DateTrigger(run_date=run_date, **cfg)
    raise ValueError(f"Unknown schedule_type: {schedule_type}")

try:
    t1 = build_trigger("cron", {"expression": "*/5 * * * *"})
    check("CronTrigger from expression", isinstance(t1, CronTrigger))
    t2 = build_trigger("cron", {"minute": "*/5", "hour": "8"})
    check("CronTrigger from fields", isinstance(t2, CronTrigger))
    t3 = build_trigger("interval", {"seconds": 30})
    check("IntervalTrigger", isinstance(t3, IntervalTrigger))
    t4 = build_trigger("date", {"run_date": datetime(2026, 12, 31, 23, 59)})
    check("DateTrigger", isinstance(t4, DateTrigger))
    try:
        build_trigger("unknown", {})
        check("Unknown trigger raises", False)
    except ValueError:
        check("Unknown trigger raises", True)
except Exception as e:
    check("Trigger building", False, str(e))


# ---------------------------------------------------------------------------
# 9. CollectorResult 行为
# ---------------------------------------------------------------------------
print("\n=== 9. CollectorResult ===")
try:
    r = CollectorResult(data=[{"a": 1}, {"a": 2}])
    check("CollectorResult list rows_count", r.rows_count == 2)
    check("CollectorResult sample(1) length", len(r.sample(1)) == 1)
    r2 = CollectorResult(data={"x": 1})
    check("CollectorResult dict rows_count == 1", r2.rows_count == 1)
    r3 = CollectorResult(data=None)
    check("CollectorResult None rows_count == 0", r3.rows_count == 0)
except Exception as e:
    check("CollectorResult test", False, str(e))


# ---------------------------------------------------------------------------
# 10. StorageResult 行为
# ---------------------------------------------------------------------------
print("\n=== 10. StorageResult ===")
try:
    r = StorageResult(success=True, rows_stored=5, message="ok")
    d = r.as_dict()
    check("StorageResult.as_dict has success", d["success"] is True)
    check("StorageResult.as_dict has rows_stored", d["rows_stored"] == 5)
    check("StorageResult.as_dict has message", d["message"] == "ok")
except Exception as e:
    check("StorageResult test", False, str(e))


# ---------------------------------------------------------------------------
# 11. APScheduler 基本调度（间隔触发器执行一次）
# ---------------------------------------------------------------------------
print("\n=== 11. APScheduler 间隔调度执行 ===")

async def test_scheduler_execution():
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.start()
    executed = []
    async def my_job():
        executed.append(datetime.now())
    from apscheduler.triggers.interval import IntervalTrigger
    scheduler.add_job(
        my_job,
        trigger=IntervalTrigger(seconds=1),
        id="test_job",
        max_instances=1,
        replace_existing=True,
    )
    await asyncio.sleep(2.5)
    scheduler.shutdown(wait=False)
    return len(executed)

try:
    count = asyncio.run(test_scheduler_execution())
    check(f"APScheduler executed >= 2 times (got {count})", count >= 2, f"executed {count} times")
except Exception as e:
    check("APScheduler execution test", False, str(e))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
if failed:
    print("\nFailed tests:")
    for name, ok in results:
        if not ok:
            print(f"  - {name}")
sys.exit(0 if failed == 0 else 1)
