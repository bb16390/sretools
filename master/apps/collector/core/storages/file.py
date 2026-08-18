"""文件存储：将采集结果写入本地/网络文件。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseStorage, StorageResult


class FileStorage(BaseStorage):
    """写入文件。

    config 字段：
        path (必填): 文件路径模板，支持 {task_id}、{date:%Y%m%d}、{time:%H%M%S} 占位符
        format: json / jsonl / csv / text，默认 json
        mode: append / overwrite / rotate，默认 append
        encoding: 默认 utf-8
        csv_dialect: excel 默认
        json_indent: 默认 2（overwrite 模式时生效）
    """

    type_name = "file"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if "path" not in config:
            raise ValueError("FileStorage config: 'path' is required")

    def _render_path(self, task_id: str) -> str:
        template = self.config["path"]
        now = datetime.now()
        return template.format(
            task_id=task_id,
            date=now,
            time=now,
            datetime=now,
            timestamp=int(now.timestamp()),
        )

    def _rows(self, data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        return [data]

    async def store(self, data: Any, *, task_id: str, log_id: int | None = None) -> StorageResult:
        path = self._render_path(task_id)
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        fmt = self.config.get("format", "json").lower()
        mode = self.config.get("mode", "append").lower()
        encoding = self.config.get("encoding", "utf-8")

        rows = self._rows(data)
        rows_count = len(rows)

        if mode == "rotate" and os.path.exists(path):
            # rotate: 改名保留旧文件
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            p = Path(path)
            p.rename(p.with_name(f"{p.stem}.{ts}{p.suffix}"))
            mode = "overwrite"

        if fmt == "json":
            content: str
            if mode == "overwrite":
                indent = self.config.get("json_indent", 2)
                content = json.dumps(rows if len(rows) > 1 else (rows[0] if rows else None),
                                     default=str, ensure_ascii=False, indent=indent)
                Path(path).write_text(content, encoding=encoding)
            else:
                # append 模式：每次 append 整个 JSON 数组 -> 改为 jsonl 更合适，这里按 jsonl 写入
                with open(path, "a", encoding=encoding) as f:
                    for r in rows:
                        f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")
        elif fmt == "jsonl":
            flag = "w" if mode == "overwrite" else "a"
            with open(path, flag, encoding=encoding) as f:
                for r in rows:
                    f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")
        elif fmt == "csv":
            import csv
            import io
            flag = "w" if mode == "overwrite" else "a"
            need_header = (flag == "w" or not os.path.exists(path) or os.path.getsize(path) == 0)
            with open(path, flag, encoding=encoding, newline="") as f:
                sample = rows[0] if rows else {}
                fields: list[str]
                if isinstance(sample, dict):
                    fields = list(sample.keys())
                else:
                    fields = ["value"]
                writer = csv.DictWriter(f, fieldnames=fields, dialect=self.config.get("csv_dialect", "excel"))
                if need_header:
                    writer.writeheader()
                for r in rows:
                    if isinstance(r, dict):
                        writer.writerow({k: r.get(k) for k in fields})
                    else:
                        writer.writerow({"value": r})
        elif fmt == "text":
            flag = "w" if mode == "overwrite" else "a"
            with open(path, flag, encoding=encoding) as f:
                for r in rows:
                    if isinstance(r, (dict, list)):
                        f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")
                    else:
                        f.write(str(r) + "\n")
        else:
            raise ValueError(f"Unknown file format: {fmt}")

        size = Path(path).stat().st_size
        return StorageResult(
            success=True, rows_stored=rows_count,
            message=f"Written to {path}",
            details={"path": path, "bytes": size},
        )

    async def close(self) -> None:
        return
