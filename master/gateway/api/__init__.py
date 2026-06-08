"""网关 HTTP API。

- GET    /api/gateway/controllers          已注册控制器清单
- GET    /api/gateway/instances            实例列表
- POST   /api/gateway/instances            新增实例（body: {id, exchange, kind, name, gateway_dir, binary_name, monitor_port, version}）
- GET    /api/gateway/instances/{id}       实例详情
- DELETE /api/gateway/instances/{id}       删除实例
- POST   /api/gateway/instances/{id}/start
- POST   /api/gateway/instances/{id}/stop
- POST   /api/gateway/instances/{id}/restart
- GET    /api/gateway/instances/{id}/status
- POST   /api/gateway/instances/{id}/deploy  multipart: file=zip archive + JSON params
- POST   /api/gateway/instances/{id}/upgrade multipart: file=zip archive + version
- POST   /api/gateway/instances/{id}/rollback body: {manifest_path}
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..core.errors import GatewayError
from ..core.models import (
    DeployParams,
    GatewayInstance,
    RollbackParams,
    UpgradeParams,
)
from ..core.store import InstanceStore, get_default_store
from ..controllers import registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


# ---------- 请求/响应模型 ----------
class InstanceCreate(BaseModel):
    id: str
    exchange: str
    kind: str
    name: str
    gateway_dir: str
    binary_name: str
    monitor_port: int
    version: str | None = None


class InstanceOut(BaseModel):
    id: str
    exchange: str
    kind: str
    name: str
    gateway_dir: str
    binary_name: str
    monitor_port: int
    version: str | None = None


class OperationOut(BaseModel):
    success: bool
    message: str
    details: dict[str, Any] | None = None
    manifest_path: str | None = None


class StatusOut(BaseModel):
    running: bool
    pid: int | None = None
    monitor_port: int
    monitor_accessible: bool = False
    gateway_dir: str = ""
    version: str | None = None
    memory_mb: float | None = None
    uptime_seconds: float | None = None


class ControllerOut(BaseModel):
    exchange: str
    kind: str
    controller: str


# ---------- 工具 ----------
def _store() -> InstanceStore:
    return get_default_store()


def _get_controller(instance_id: str):
    inst = _store().get(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"instance {instance_id} not found")
    try:
        cls = registry.get(inst.exchange, inst.kind)
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"未注册控制器: exchange={inst.exchange}, kind={inst.kind}",
        ) from exc
    # 计算安装/备份根：优先使用实例 gateway_dir 的上层；否则使用默认 data/gateways
    install_root = Path(inst.gateway_dir).parent
    backup_root = install_root.parent / "backup" / inst.id if install_root else Path("data/gateways/backup") / inst.id
    return inst, cls(inst, install_root, backup_root)


def _wrap_error(exc: Exception) -> None:
    if isinstance(exc, GatewayError):
        raise HTTPException(status_code=400, detail={
            "code": getattr(exc, "code", "E9999"),
            "message": exc.message,
            "details": exc.details,
        })
    raise HTTPException(status_code=500, detail=str(exc))


# ---------- 路由 ----------
@router.get("/controllers", response_model=list[ControllerOut])
def list_controllers():
    return [
        {"exchange": e, "kind": k, "controller": cls}
        for e, k, cls in registry.list_all()
    ]


@router.get("/instances", response_model=list[InstanceOut])
def list_instances():
    return [
        {
            "id": i.id,
            "exchange": i.exchange,
            "kind": i.kind,
            "name": i.name,
            "gateway_dir": i.gateway_dir,
            "binary_name": i.binary_name,
            "monitor_port": i.monitor_port,
            "version": i.version,
        }
        for i in _store().list()
    ]


@router.post("/instances", response_model=InstanceOut)
def create_instance(payload: InstanceCreate):
    inst = GatewayInstance(
        id=payload.id,
        exchange=payload.exchange.lower(),
        kind=payload.kind.lower(),
        name=payload.name,
        gateway_dir=payload.gateway_dir,
        binary_name=payload.binary_name,
        monitor_port=payload.monitor_port,
        version=payload.version,
    )
    _store().upsert(inst)
    return {
        "id": inst.id,
        "exchange": inst.exchange,
        "kind": inst.kind,
        "name": inst.name,
        "gateway_dir": inst.gateway_dir,
        "binary_name": inst.binary_name,
        "monitor_port": inst.monitor_port,
        "version": inst.version,
    }


@router.get("/instances/{instance_id}", response_model=InstanceOut)
def get_instance(instance_id: str):
    inst = _store().get(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="instance not found")
    return {
        "id": inst.id,
        "exchange": inst.exchange,
        "kind": inst.kind,
        "name": inst.name,
        "gateway_dir": inst.gateway_dir,
        "binary_name": inst.binary_name,
        "monitor_port": inst.monitor_port,
        "version": inst.version,
    }


@router.delete("/instances/{instance_id}", response_model=dict)
def delete_instance(instance_id: str):
    if not _store().delete(instance_id):
        raise HTTPException(status_code=404, detail="instance not found")
    return {"deleted": instance_id}


@router.post("/instances/{instance_id}/start", response_model=OperationOut)
def start_instance(instance_id: str):
    _inst, controller = _get_controller(instance_id)
    try:
        result = controller.start()
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 start 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    return result.as_dict()


@router.post("/instances/{instance_id}/stop", response_model=OperationOut)
def stop_instance(instance_id: str, force: bool = False):
    _inst, controller = _get_controller(instance_id)
    try:
        result = controller.stop(force=force)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 stop 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    return result.as_dict()


@router.post("/instances/{instance_id}/restart", response_model=OperationOut)
def restart_instance(instance_id: str):
    _inst, controller = _get_controller(instance_id)
    try:
        result = controller.restart()
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 restart 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    return result.as_dict()


@router.get("/instances/{instance_id}/status", response_model=StatusOut)
def get_instance_status(instance_id: str):
    _inst, controller = _get_controller(instance_id)
    try:
        status = controller.status()
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 status 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    return status.as_dict()


@router.post("/instances/{instance_id}/deploy", response_model=OperationOut)
async def deploy_instance(
    instance_id: str,
    file: UploadFile = File(...),
    gwid: str = Form(...),
    password: str = Form(""),
    env_id: int = Form(0),
    level: int = Form(2),
    access_mode: str = Form("TCP"),
    line_type: str = Form("地面"),
    local_ip: str = Form("127.0.0.1"),
):
    inst, controller = _get_controller(instance_id)

    # 保存上传的 zip 到临时文件
    archive_bytes = await file.read()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(archive_bytes)
            tmp_path = Path(tmp.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"保存上传文件失败: {exc}")

    try:
        params = DeployParams(
            gwid=gwid,
            password=password,
            env_id=env_id,
            level=level,
            access_mode=access_mode,
            line_type=line_type,
            local_ip=local_ip,
        )
        result = controller.deploy(tmp_path, params)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 deploy 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass

    # 如果成功且 controller 报告成功，同步实例版本信息
    if result.success and result.details and result.details.get("version"):
        inst.version = result.details["version"]
        _store().upsert(inst)
    return result.as_dict()


@router.post("/instances/{instance_id}/upgrade", response_model=OperationOut)
async def upgrade_instance(
    instance_id: str,
    file: UploadFile = File(...),
    version: str | None = Form(None),
    timeout: int = Form(300),
):
    _inst, controller = _get_controller(instance_id)
    archive_bytes = await file.read()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(archive_bytes)
            tmp_path = Path(tmp.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"保存上传文件失败: {exc}")

    try:
        result = controller.upgrade(
            UpgradeParams(new_archive=str(tmp_path), version=version, timeout=timeout)
        )
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 upgrade 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
    return result.as_dict()


@router.post("/instances/{instance_id}/rollback", response_model=OperationOut)
def rollback_instance(instance_id: str, payload: dict[str, Any] | None = None):
    _inst, controller = _get_controller(instance_id)
    manifest_path = (payload or {}).get("manifest_path")
    if not manifest_path:
        raise HTTPException(status_code=400, detail="manifest_path required")
    try:
        result = controller.rollback(RollbackParams(manifest_path=str(manifest_path)))
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该控制器未实现 rollback 操作")
    except Exception as exc:  # noqa: BLE001
        _wrap_error(exc)
    return result.as_dict()
