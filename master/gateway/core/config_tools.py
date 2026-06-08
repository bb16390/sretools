"""配置模板选择、变量替换、server_list.xml 生成、版本解析工具。

所有函数均为纯函数，便于单元测试。
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .errors import ConfigError

ENV_MAP: dict[int, str] = {
    0: "生产环境",
    1: "期权全真环境",
    2: "联网测试环境",
}

_VERSION_RE = re.compile(r"(20\d{6})")


def select_mdgw_template(
    sample_dir: Path,
    env_id: int,
    level: int,
    access_mode: str,
    line_type: str = "地面",
) -> Path:
    """选择 mdgw 的 config.xml.sample。

    找不到匹配的模板时，返回 sample_dir 中第一个 *.config.xml.sample* 文件；
    若仍找不到，则抛 ConfigError。
    """
    env = ENV_MAP.get(env_id, "生产环境")
    candidates: list[str] = []
    mode = (access_mode or "TCP").upper()

    if mode == "UDP":
        candidates.append(f"{env}.config.xml.sample.UDP.Level{level}")
        if level == 1:
            candidates.append(f"{env}.config.xml.sample.UDP.地面")
    else:  # TCP
        if level == 2:
            candidates.append(f"{env}.config.xml.sample.Level2")
        else:
            candidates.append(f"{env}.config.xml.sample.Level1.{line_type}")
            candidates.append(f"{env}.config.xml.sample.Level1.地面")

    for name in candidates:
        p = sample_dir / name
        if p.exists() and p.is_file():
            return p

    # 回退：列出目录中的所有 sample 文件
    fallback = sorted(
        p for p in sample_dir.glob("*.config.xml.sample*") if p.is_file()
    )
    if fallback:
        return fallback[0]

    raise ConfigError(
        "E1001",
        f"未在 {sample_dir} 找到匹配的配置模板 (env={env}, level={level}, "
        f"mode={mode}, line_type={line_type})",
    )


def select_tgw_template(sample_dir: Path, env_id: int) -> Path:
    """选择 tgw 的 config.xml.sample（按环境名优先，否则取首个 sample）。"""
    env = ENV_MAP.get(env_id, "生产环境")
    candidate = sample_dir / f"{env}.config.xml.sample"
    if candidate.exists() and candidate.is_file():
        return candidate
    fallback = sorted(
        p for p in sample_dir.glob("*.config.xml.sample*") if p.is_file()
    )
    if fallback:
        return fallback[0]
    raise ConfigError("E1002", f"未在 {sample_dir} 找到 tgw 的配置模板")


def render_config(
    template_path: Path,
    replacements: dict[str, str],
    output_path: Path,
) -> Path:
    """基于文本的占位符替换。相比 XML 解析，可兼容模板中未闭合的节点。"""
    if not template_path.exists():
        raise ConfigError("E1003", f"模板文件不存在: {template_path}")

    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(key, str(value))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path


def generate_server_list_xml(
    output_path: Path,
    groups: list[dict[str, Any]],
) -> Path:
    """生成 tgw 20240823+ 的独立 server_list.xml。"""
    root = ET.Element("server_list")

    for group in groups or []:
        no = str(group.get("no", ""))
        group_elem = ET.SubElement(root, "group", {"no": no})

        for server in group.get("servers", []) or []:
            server_elem = ET.SubElement(group_elem, "server")
            desc = ET.SubElement(server_elem, "description")
            desc.text = str(server.get("description", ""))
            addr = ET.SubElement(server_elem, "address")
            addr.text = str(server.get("address", ""))
            port_elem = ET.SubElement(server_elem, "port")
            port_elem.text = str(server.get("port", 7019))
            knock = ET.SubElement(server_elem, "knock_offset_time")
            knock.text = str(server.get("knock_offset_time", 0))

    ET.indent(root, space="  ")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    return output_path


def extract_version_from_archive(archive_path: str | Path) -> str:
    """从 zip 文件名中解析 YYYYMMDD 版本号；失败返回 'unknown'。"""
    stem = Path(archive_path).name
    match = _VERSION_RE.search(stem)
    if match:
        return match.group(1)

    # 尝试读取 zip 内部 changelog / readme 的文件名
    try:
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                m = _VERSION_RE.search(name)
                if m:
                    return m.group(1)
    except (zipfile.BadZipFile, OSError):
        pass

    return "unknown"


def find_binary_in_zip(archive_path: str | Path, binary_name: str) -> str | None:
    """在 zip 中查找名为 binary_name 的文件路径，返回 zip 内相对路径或 None。"""
    try:
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                tail = Path(name).name
                if tail == binary_name:
                    return name
    except (zipfile.BadZipFile, OSError):
        return None
    return None
