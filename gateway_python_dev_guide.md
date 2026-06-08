# 深交所网关部署、升级、启停 Python 开发指南

> **文档定位**: 本指南作为 Python 网关管理工具的 spec 文档，涵盖行情网关(mdgw)和交易网关(tgw)的自动化部署、升级、启停管理方案。
> **目标读者**: 运维开发人员、系统集成工程师
> **Python版本**: 3.8+

---

## 目录

- [第1章 网关程序概述](#第1章-网关程序概述)
  - [1.1 行情网关 mdgw](#11-行情网关-mdgw)
  - [1.2 交易网关 tgw](#12-交易网关-tgw)
  - [1.3 共性特征总结](#13-共性特征总结)
- [第2章 部署指南](#第2章-部署指南)
  - [2.1 目录结构规范](#21-目录结构规范)
  - [2.2 环境检查](#22-环境检查)
  - [2.3 配置文件生成](#23-配置文件生成)
  - [2.4 部署代码实现](#24-部署代码实现)
- [第3章 升级指南](#第3章-升级指南)
  - [3.1 升级前检查](#31-升级前检查)
  - [3.2 mdgw 升级流程](#32-mdgw-升级流程)
  - [3.3 tgw 升级流程](#33-tgw-升级流程)
  - [3.4 回滚机制](#34-回滚机制)
- [第4章 启停管理](#第4章-启停管理)
  - [4.1 进程管理策略](#41-进程管理策略)
  - [4.2 启动流程](#42-启动流程)
  - [4.3 停止流程](#43-停止流程)
  - [4.4 状态检查](#44-状态检查)
  - [4.5 批量管理](#45-批量管理)
- [第5章 配置文件解析与生成](#第5章-配置文件解析与生成)
  - [5.1 数据模型定义](#51-数据模型定义)
  - [5.2 XML 解析器](#52-xml-解析器)
  - [5.3 配置校验器](#53-配置校验器)
  - [5.4 配置迁移工具](#54-配置迁移工具)
- [第6章 错误处理与日志](#第6章-错误处理与日志)
  - [6.1 错误分类体系](#61-错误分类体系)
  - [6.2 自定义异常类](#62-自定义异常类)
  - [6.3 日志配置](#63-日志配置)
  - [6.4 操作审计日志](#64-操作审计日志)
- [第7章 完整使用示例](#第7章-完整使用示例)
  - [7.1 部署 mdgw 示例](#71-部署-mdgw-示例)
  - [7.2 部署 tgw 示例](#72-部署-tgw-示例)
  - [7.3 升级 tgw 示例](#73-升级-tgw-示例)
  - [7.4 日常启停示例](#74-日常启停示例)
  - [7.5 CLI 命令行工具](#75-cli-命令行工具)

---

## 第1章 网关程序概述

### 1.1 行情网关 mdgw

mdgw（Market Data Gateway）是深交所行情网关，用于接收深交所行情组播数据并转发给下游客户端。

#### 版本矩阵

| 版本号 | 平台 | 二进制文件名 | 大小 | 特性说明 |
|--------|------|-------------|------|---------|
| 20230609 | Linux x86_64 | `mdgw` | ~9.6 MB | UDP应用层分包、TCP网关缓存模式 |
| 20240502 | Linux x86_64 | `mdgw` | ~10.5 MB | MDDP协议分片、信创支持 |
| 20240502 | 银河麒麟V10 x86_64 | `mdgw` | ~10.0 MB | 信创版本 |

> 注：`mdgw_20240722_linux.zip` 和 `mdgw_20240722_ky10_x86.zip` 的 zip 包名标注为 20240722，但内部 changelog 版本号为 20240502。

#### 架构类型

- **NETWORK（网络版）**: 支持 TCP/UDP 接入，支持重传服务，支持 SSL 认证
- **LIVE（现场版）**: 仅支持 TCP 接入，无重传服务，无 SSL 认证（auth_mode=0）

#### 协议与接入方式

| 协议 | 接入模式 | 说明 |
|------|---------|------|
| STEP | TCP | 文本协议，Level1/Level2 |
| BINARY | TCP | 二进制协议，Level2 |
| BINARY | UDP | 组播分发模式，仅 Level1/Level2 |

#### 端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| 实时行情服务 | 8016 | TCP 模式实时行情推送 |
| 重传服务 | 8018 | 历史行情重传请求 |
| 监控服务 | 7501 | 网关状态监控接口 |

#### 配置 Sample 清单

mdgw 每个版本包含 **14 个配置文件 sample**，命名规则为：`{环境}.config.xml.sample.{Level}.{线路类型}`

| 环境 | Level1.卫星 | Level1.地面 | Level1.地面高速 | Level2 | UDP.Level1.地面 | UDP.Level2 | UDP.地面 |
|------|-------------|-------------|-----------------|--------|-----------------|------------|----------|
| 生产环境 | 有 | 有 | -- | 有 | 有 | 有 | -- |
| 联网测试环境 | 有 | 有 | -- | 有 | -- | 有 | 有 |
| 期权全真环境 | 有 | -- | 有 | 有 | -- | -- | -- |

#### 关键配置项

```xml
<config>
    <protocol>STEP</protocol>              <!-- STEP 或 BINARY -->
    <id>__GWID__</id>                     <!-- 网关ID，需替换 -->
    <type>NETWORK</type>                   <!-- NETWORK 或 LIVE -->
    <password>__GWID__</password>          <!-- 密码 -->
    <env_id>0</env_id>                    <!-- 0=生产, 1=期权全真, 2=联网测试 -->
    <auth_mode>1</auth_mode>               <!-- 0=TCP, 1=SSL无证书, 2=SSL文件证书, 3=SSL EKey -->
    <ca_file>ca.crt</ca_file>
    <auto_clean>
        <enable>1</enable>
        <keep_days>14</keep_days>
    </auto_clean>
    <!-- 通信服务器(组播接收) -->
    <comm_server>
        <igmp_version>V3</igmp_version>
        <line_type_list>...</line_type_list>
        <admin_service>...</admin_service>
        <resend_service>...</resend_service>
    </comm_server>
    <!-- 用户接入 -->
    <access_user>
        <realtime_service_list>...</realtime_service_list>
        <resend_service>...</resend_service>
    </access_user>
    <!-- 监控服务 -->
    <monitor_service>
        <port>7501</port>
        <password>password</password>
    </monitor_service>
</config>
```

UDP 模式额外包含：

```xml
<access_mode>UDP</access_mode>
<udp_send_speed>0</udp_send_speed>
<news_path>./news_path</news_path>
<blocked_channel_list>...</blocked_channel_list>
```

---

### 1.2 交易网关 tgw

tgw（Trading Gateway）是深交所交易网关，用于连接深交所交易系统与客户端交易程序。

#### 版本矩阵

| 版本号 | 平台 | 二进制文件名 | 大小 | 特性说明 |
|--------|------|-------------|------|---------|
| 20211101 | Linux x86_64 | `tgw` | ~8.5 MB | server_list 内嵌于 config.xml |
| 20240823 | Linux x86_64 | `tgw` | ~8.6 MB | server_list 独立为 server_list.xml，支持信创 |

#### 平台端口规划

| 平台ID | 平台名称 | 端口 |
|--------|---------|------|
| 1 | 现货集中竞价交易平台 | 8019 |
| 2 | 综合金融服务平台 | 8020 |
| 3 | 非交易处理平台 | 8021 |
| 4 | 衍生品集中竞价交易平台 | 8022 |
| 5 | 国际市场互联平台 | 8023 |
| 6 | 固定收益交易平台 | 8024 |
| - | 监控服务 | 7500 |

#### 20211101 vs 20240823 关键差异

| 差异项 | 20211101 | 20240823 |
|--------|----------|----------|
| server_list 位置 | config.xml 内嵌 `<server_list>` | 独立 `server_list.xml` |
| 服务器分组 | 单组（主+备） | 最多 4 组（group no=1~4） |
| 密码字段 | `__GWID__`（与 ID 相同） | `__PASSWORD__`（监控界面生成） |
| block_cc_report | 存在 | **已移除**（改由服务端配置） |
| 固定收益平台(id=6) | 注释状态 | 默认启用 |
| 信创支持 | 无 | 有 |

#### 20240823 配置文件结构

**config.xml**:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
    <protocol>BINARY</protocol>
    <id>__GWID__</id>
    <env_id>0</env_id>                    <!-- 0=生产, 1=期权全真, 2=联网测试 -->
    <auto_clean>
        <enable>0</enable>
        <keep_days>14</keep_days>
    </auto_clean>
    <data_persistence>
        <server_enable>0</server_enable>
        <user_enable>0</user_enable>
    </data_persistence>
    <tgw_list>
        <tgw>
            <id>__GWID__</id>
            <password>__PASSWORD__</password>
            <auth_mode>1</auth_mode>
            <ca_file>ca.crt</ca_file>
            <is_aggregation>0</is_aggregation>
            <!-- server_list 已移除，改由独立文件管理 -->
        </tgw>
    </tgw_list>
    <access_user>
        <password>__PASSWORD__</password>
        <platform_list>
            <platform><id>1</id><interface>0.0.0.0</interface><port>8019</port></platform>
            <platform><id>2</id><interface>0.0.0.0</interface><port>8020</port></platform>
            <platform><id>3</id><interface>0.0.0.0</interface><port>8021</port></platform>
            <platform><id>4</id><interface>0.0.0.0</interface><port>8022</port></platform>
            <platform><id>5</id><interface>0.0.0.0</interface><port>8023</port></platform>
            <platform><id>6</id><interface>0.0.0.0</interface><port>8024</port></platform>
        </platform_list>
    </access_user>
    <monitor_service>
        <port>7500</port>
        <password>password</password>
    </monitor_service>
</config>
```

**server_list.xml**（20240823+ 新增）:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<server_list>
    <group no="1">
        <server>
            <description>主用服务器地址</description>
            <address>__GROUP_1_MAIN_SERVER_IP__</address>
            <port>7019</port>
            <knock_offset_time>0</knock_offset_time>
        </server>
        <server>
            <description>备用服务器地址</description>
            <address>__GROUP_1_BKUP_SERVER_IP__</address>
            <port>7019</port>
            <knock_offset_time>0</knock_offset_time>
        </server>
    </group>
    <!-- 最多支持 4 组 -->
</server_list>
```

---

### 1.3 共性特征总结

| 特征项 | mdgw | tgw |
|--------|------|-----|
| 二进制类型 | ELF 64-bit LSB executable | ELF 64-bit LSB executable |
| 启动方式 | 直接运行 `./mdgw` | 直接运行 `./tgw` |
| 配置文件 | `cfg/config.xml` + `cfg/ca.crt` | `cfg/config.xml` + `cfg/ca.crt` + `cfg/server_list.xml`(20240823+) |
| SSL 认证模式 | auth_mode 0/1/2/3 | auth_mode 0/1/2/3 |
| 日志清理 | auto_clean (enable + keep_days) | auto_clean (enable + keep_days) |
| 数据持久化 | data_persistence | data_persistence |
| 监控服务 | monitor_service (port=7501) | monitor_service (port=7500) |
| 环境标识 | env_id: 0=生产, 1=期权全真, 2=联网测试 | env_id: 0=生产, 1=期权全真, 2=联网测试 |
| 第三方依赖 | OpenSSL, JsonCpp | OpenSSL, JsonCpp |
| 工作目录 | 二进制所在目录（程序查找 `./cfg/`） | 二进制所在目录（程序查找 `./cfg/`） |

---

## 第2章 部署指南

### 2.1 目录结构规范

```
/opt/gateway/
├── mdgw/
│   ├── mdgw                          # 二进制文件（chmod +x）
│   ├── cfg/
│   │   ├── config.xml                # 主配置文件
│   │   └── ca.crt                    # CA 证书
│   ├── logs/                         # 运行日志（程序自动生成）
│   └── news_path/                    # 公告落地目录（仅 mdgw UDP 模式）
├── tgw/
│   ├── tgw                           # 二进制文件（chmod +x）
│   ├── cfg/
│   │   ├── config.xml                # 主配置文件
│   │   ├── server_list.xml           # 服务器列表（仅 20240823+）
│   │   └── ca.crt                    # CA 证书
│   └── logs/                         # 运行日志
├── backup/                           # 配置备份目录
└── versions/                         # 版本归档目录
```

---

### 2.2 环境检查

部署前需执行以下检查项：

#### 检查清单

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 操作系统类型 | `/etc/os-release` | Linux x86_64 或 麒麟V10 |
| 动态库依赖 | `ldd <binary>` | 所有 `.so` 均可解析 |
| 端口占用 | `psutil.net_connections()` 或 `socket.bind()` | 目标端口未被占用 |
| 文件权限 | `os.access(path, os.X_OK)` | 二进制有执行权限 |
| 磁盘空间 | `shutil.disk_usage()` | 剩余空间 > 1GB |
| CA 证书 | `os.path.exists()` | `cfg/ca.crt` 存在 |

#### Python 实现

```python
import os
import platform
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    detail: str = ""


class PreflightChecker:
    """网关部署前环境检查器"""

    def __init__(self, gateway_dir: str, ports: List[int]):
        self.gateway_dir = gateway_dir
        self.ports = ports
        self.binary_name = os.path.basename(gateway_dir)  # mdgw 或 tgw
        self.binary_path = os.path.join(gateway_dir, self.binary_name)

    def check_all(self) -> List[CheckResult]:
        """执行全部检查项"""
        results = []
        results.append(self.check_os())
        results.append(self.check_binary_exists())
        results.append(self.check_binary_executable())
        results.append(self.check_dependencies())
        results.append(self.check_ports())
        results.append(self.check_disk_space())
        results.append(self.check_ca_cert())
        return results

    def check_os(self) -> CheckResult:
        """检查操作系统类型（含信创环境）"""
        system = platform.system()
        machine = platform.machine()

        if system != "Linux":
            return CheckResult("OS", False, f"不支持的操作系统: {system}")

        # 检测信创环境（麒麟V10）
        kylin = False
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                content = f.read()
                if "kylin" in content.lower() or "麒麟" in content:
                    kylin = True

        arch_ok = machine in ("x86_64", "aarch64")
        msg = f"{system} {machine}"
        if kylin:
            msg += " (麒麟V10信创环境)"

        return CheckResult("OS", arch_ok, msg)

    def check_binary_exists(self) -> CheckResult:
        """检查二进制文件是否存在"""
        exists = os.path.exists(self.binary_path)
        return CheckResult(
            "Binary",
            exists,
            f"二进制文件{'存在' if exists else '不存在'}: {self.binary_path}"
        )

    def check_binary_executable(self) -> CheckResult:
        """检查二进制是否有执行权限"""
        executable = os.access(self.binary_path, os.X_OK)
        return CheckResult(
            "Permission",
            executable,
            f"执行权限{'已授予' if executable else '未授予'}"
        )

    def check_dependencies(self) -> CheckResult:
        """检查动态库依赖（使用 ldd）"""
        try:
            result = subprocess.run(
                ["ldd", self.binary_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return CheckResult("Dependencies", False, "ldd 执行失败", result.stderr)

            missing = []
            for line in result.stdout.splitlines():
                if "not found" in line:
                    lib = line.split("=>")[0].strip()
                    missing.append(lib)

            if missing:
                return CheckResult(
                    "Dependencies",
                    False,
                    f"缺失 {len(missing)} 个动态库",
                    ", ".join(missing)
                )
            return CheckResult("Dependencies", True, "所有动态库依赖已满足")
        except FileNotFoundError:
            return CheckResult("Dependencies", False, "ldd 命令未找到")
        except subprocess.TimeoutExpired:
            return CheckResult("Dependencies", False, "ldd 执行超时")

    def check_ports(self) -> CheckResult:
        """检查目标端口是否被占用"""
        occupied = []
        for port in self.ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("0.0.0.0", port))
            except OSError:
                occupied.append(str(port))

        if occupied:
            return CheckResult(
                "Ports",
                False,
                f"端口被占用: {', '.join(occupied)}"
            )
        return CheckResult("Ports", True, "所有目标端口可用")

    def check_disk_space(self) -> CheckResult:
        """检查磁盘空间"""
        usage = shutil.disk_usage(self.gateway_dir)
        free_gb = usage.free / (1024 ** 3)
        ok = free_gb > 1.0
        return CheckResult(
            "Disk",
            ok,
            f"剩余磁盘空间: {free_gb:.2f} GB",
            "" if ok else "需要至少 1GB 可用空间"
        )

    def check_ca_cert(self) -> CheckResult:
        """检查 CA 证书是否存在"""
        ca_path = os.path.join(self.gateway_dir, "cfg", "ca.crt")
        exists = os.path.exists(ca_path)
        return CheckResult(
            "CA Cert",
            exists,
            f"CA证书{'存在' if exists else '不存在'}: {ca_path}"
        )
```

---

### 2.3 配置文件生成

#### mdgw 配置模板选择算法

```python
from pathlib import Path
from typing import Optional


class MdgwTemplateSelector:
    """mdgw 配置模板选择器"""

    # 环境映射
    ENV_MAP = {
        0: "生产环境",
        1: "期权全真环境",
        2: "联网测试环境"
    }

    @staticmethod
    def select_template(
        sample_dir: Path,
        env_id: int,
        level: int,           # 1 或 2
        access_mode: str,     # "TCP" 或 "UDP"
        line_type: str = "地面"  # "卫星", "地面", "地面高速"
    ) -> Path:
        """
        根据参数选择对应的 config.xml.sample 文件

        命名规则: {环境}.config.xml.sample[.Level{level}][.{线路类型}]
        """
        env_name = MdgwTemplateSelector.ENV_MAP.get(env_id, "生产环境")

        # 构建候选文件名列表（按优先级排序）
        candidates = []

        if access_mode == "UDP":
            # UDP 模式: 生产环境.config.xml.sample.UDP.Level2
            candidates.append(
                f"{env_name}.config.xml.sample.UDP.Level{level}"
            )
            if level == 1:
                candidates.append(
                    f"{env_name}.config.xml.sample.UDP.地面"
                )
        else:
            # TCP 模式
            if level == 2:
                candidates.append(f"{env_name}.config.xml.sample.Level2")
            else:
                # Level1 需要区分线路类型
                if line_type == "地面高速":
                    candidates.append(
                        f"{env_name}-config.xml.sample.Level1.地面高速"
                    )
                candidates.append(
                    f"{env_name}.config.xml.sample.Level1.{line_type}"
                )
                candidates.append(
                    f"{env_name}.config.xml.sample.Level1.地面"
                )

        # 查找第一个存在的文件
        for candidate in candidates:
            path = sample_dir / candidate
            if path.exists():
                return path

        # 回退：列出目录中的文件，进行模糊匹配
        available = list(sample_dir.glob("*.config.xml.sample*"))
        raise FileNotFoundError(
            f"未找到匹配的配置模板。参数: env={env_name}, level={level}, "
            f"mode={access_mode}, line={line_type}。"
            f"可用模板: {[p.name for p in available]}"
        )
```

#### 占位符替换

```python
import xml.etree.ElementTree as ET
from pathlib import Path


class ConfigGenerator:
    """配置文件生成器"""

    @staticmethod
    def generate_mdgw_config(
        template_path: Path,
        output_path: Path,
        gwid: str,
        local_ip: str,
        **kwargs
    ) -> None:
        """
        基于模板生成 mdgw 配置文件

        Args:
            template_path: sample 模板路径
            output_path: 输出配置文件路径
            gwid: 网关ID
            local_ip: 本地接收网卡IP（UDP模式需要）
            **kwargs: 其他自定义配置项
        """
        tree = ET.parse(template_path)
        root = tree.getroot()

        # 替换所有占位符
        for elem in root.iter():
            if elem.text:
                elem.text = elem.text.replace("__GWID__", gwid)
                elem.text = elem.text.replace("__RE_LOCAL_IP__", local_ip)

            # 处理属性中的占位符
            for attr_name, attr_value in elem.attrib.items():
                elem.set(
                    attr_name,
                    attr_value.replace("__GWID__", gwid)
                              .replace("__RE_LOCAL_IP__", local_ip)
                )

        # 应用自定义配置项
        for key, value in kwargs.items():
            elem = root.find(key)
            if elem is not None:
                elem.text = str(value)

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    @staticmethod
    def generate_tgw_config(
        template_path: Path,
        output_path: Path,
        gwid: str,
        password: str,
        **kwargs
    ) -> None:
        """基于模板生成 tgw 配置文件"""
        tree = ET.parse(template_path)
        root = tree.getroot()

        for elem in root.iter():
            if elem.text:
                elem.text = elem.text.replace("__GWID__", gwid)
                elem.text = elem.text.replace("__PASSWORD__", password)

        for key, value in kwargs.items():
            elem = root.find(key)
            if elem is not None:
                elem.text = str(value)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    @staticmethod
    def generate_server_list(
        output_path: Path,
        groups: list  # [{"no": "1", "servers": [{"address": "...", "port": 7019, ...}]}]
    ) -> None:
        """生成 tgw server_list.xml"""
        root = ET.Element("server_list")

        for group_data in groups:
            group = ET.SubElement(root, "group", no=group_data["no"])
            for server_data in group_data.get("servers", []):
                server = ET.SubElement(group, "server")
                desc = ET.SubElement(server, "description")
                desc.text = server_data.get("description", "")
                addr = ET.SubElement(server, "address")
                addr.text = server_data["address"]
                port = ET.SubElement(server, "port")
                port.text = str(server_data.get("port", 7019))
                knock = ET.SubElement(server, "knock_offset_time")
                knock.text = str(server_data.get("knock_offset_time", 0))

        ET.indent(root, space="  ")
        tree = ET.ElementTree(root)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="UTF-8", xml_declaration=True)
```

---

### 2.4 部署代码实现

```python
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class DeploymentResult:
    success: bool
    gateway_type: str  # "mdgw" 或 "tgw"
    gateway_dir: Path
    config_path: Optional[Path] = None
    server_list_path: Optional[Path] = None
    message: str = ""


class GatewayDeployer:
    """网关部署器"""

    def __init__(self, gateway_type: str, install_dir: Path):
        self.gateway_type = gateway_type  # "mdgw" 或 "tgw"
        self.install_dir = install_dir
        self.gateway_dir = install_dir / gateway_type
        self.backup_dir = install_dir / "backup"
        self.versions_dir = install_dir / "versions"

    def deploy(
        self,
        archive_path: Path,
        config_params: dict,
        server_list_groups: Optional[list] = None
    ) -> DeploymentResult:
        """
        执行完整部署流程

        Args:
            archive_path: 网关 zip 包路径
            config_params: 配置参数（gwid, password, env_id 等）
            server_list_groups: tgw 20240823+ 的服务器分组配置
        """
        try:
            # 1. 解压归档
            self._extract_archive(archive_path)

            # 2. 环境检查
            ports = self._get_default_ports()
            checker = PreflightChecker(str(self.gateway_dir), ports)
            results = checker.check_all()
            failures = [r for r in results if not r.passed]
            if failures:
                msgs = "; ".join(f"{r.name}: {r.message}" for r in failures)
                return DeploymentResult(False, self.gateway_type, self.gateway_dir, message=msgs)

            # 3. 生成配置文件
            cfg_dir = self.gateway_dir / "cfg"
            sample_dir = cfg_dir

            # 选择模板并生成 config.xml
            if self.gateway_type == "mdgw":
                template = MdgwTemplateSelector.select_template(
                    sample_dir,
                    config_params.get("env_id", 0),
                    config_params.get("level", 2),
                    config_params.get("access_mode", "TCP"),
                    config_params.get("line_type", "地面")
                )
                config_path = cfg_dir / "config.xml"
                ConfigGenerator.generate_mdgw_config(
                    template, config_path,
                    config_params["gwid"],
                    config_params.get("local_ip", "0.0.0.0"),
                    **config_params.get("overrides", {})
                )
            else:  # tgw
                template = cfg_dir / f"生产环境.config.xml.sample"
                if not template.exists():
                    template = cfg_dir / f"联网测试环境.config.xml.sample"
                config_path = cfg_dir / "config.xml"
                ConfigGenerator.generate_tgw_config(
                    template, config_path,
                    config_params["gwid"],
                    config_params["password"],
                    **config_params.get("overrides", {})
                )

                # 生成 server_list.xml（tgw 20240823+）
                if server_list_groups:
                    server_list_path = cfg_dir / "server_list.xml"
                    ConfigGenerator.generate_server_list(server_list_path, server_list_groups)
                else:
                    server_list_path = None

            # 4. 设置执行权限
            binary_path = self.gateway_dir / self.gateway_type
            binary_path.chmod(binary_path.stat().st_mode | 0o111)

            return DeploymentResult(
                True, self.gateway_type, self.gateway_dir,
                config_path=config_path,
                server_list_path=server_list_path,
                message="部署成功"
            )

        except Exception as e:
            return DeploymentResult(
                False, self.gateway_type, self.gateway_dir,
                message=f"部署失败: {str(e)}"
            )

    def _extract_archive(self, archive_path: Path) -> None:
        """解压 zip 包到安装目录"""
        self.gateway_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, 'r') as z:
            # 获取 zip 包内的根目录名
            root_dir = z.namelist()[0].split('/')[0]
            z.extractall(self.install_dir)
            # 将解压后的内容移动到标准目录
            extracted = self.install_dir / root_dir
            if extracted.exists() and extracted != self.gateway_dir:
                # 合并内容
                for item in extracted.iterdir():
                    dest = self.gateway_dir / item.name
                    if dest.exists():
                        shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
                    shutil.move(str(item), str(dest))
                extracted.rmdir()

    def _get_default_ports(self) -> List[int]:
        """获取默认端口列表"""
        if self.gateway_type == "mdgw":
            return [8016, 8018, 7501]
        else:
            return [8019, 8020, 8021, 8022, 8023, 8024, 7500]
```

---

## 第3章 升级指南

### 3.1 升级前检查

```python
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class BackupManifest:
    """备份清单"""
    timestamp: str
    gateway_type: str
    gateway_dir: Path
    binary_backup: Path
    config_backup: Path
    server_list_backup: Optional[Path]
    version: str


class GatewayUpgrader:
    """网关升级器"""

    def __init__(self, gateway_type: str, gateway_dir: Path, backup_dir: Path):
        self.gateway_type = gateway_type
        self.gateway_dir = Path(gateway_dir)
        self.backup_dir = Path(backup_dir)
        self.binary_path = self.gateway_dir / gateway_type
        self.config_path = self.gateway_dir / "cfg" / "config.xml"
        self.server_list_path = self.gateway_dir / "cfg" / "server_list.xml"

    def detect_current_version(self) -> str:
        """
        检测当前安装的版本
        策略: 从二进制文件读取版本字符串，或从版本记录文件读取
        """
        # 方法1: 尝试从二进制中读取版本字符串
        try:
            result = subprocess.run(
                ["strings", str(self.binary_path)],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if line.startswith("20") and len(line) == 8 and line.isdigit():
                    return line
        except FileNotFoundError:
            pass

        # 方法2: 从版本记录文件读取
        version_file = self.gateway_dir / ".version"
        if version_file.exists():
            return version_file.read_text().strip()

        return "unknown"

    def backup(self) -> BackupManifest:
        """备份当前配置和二进制"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = self.backup_dir / f"{self.gateway_type}_{timestamp}"
        backup_subdir.mkdir(parents=True, exist_ok=True)

        # 备份二进制
        binary_backup = backup_subdir / self.binary_path.name
        shutil.copy2(self.binary_path, binary_backup)

        # 备份配置
        config_backup = backup_subdir / "config.xml"
        shutil.copy2(self.config_path, config_backup)

        # 备份 server_list.xml（如果存在）
        server_list_backup = None
        if self.server_list_path.exists():
            server_list_backup = backup_subdir / "server_list.xml"
            shutil.copy2(self.server_list_path, server_list_backup)

        # 保存版本信息
        version = self.detect_current_version()
        manifest = BackupManifest(
            timestamp=timestamp,
            gateway_type=self.gateway_type,
            gateway_dir=self.gateway_dir,
            binary_backup=binary_backup,
            config_backup=config_backup,
            server_list_backup=server_list_backup,
            version=version
        )

        manifest_path = backup_subdir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(asdict(manifest), f, indent=2, default=str)

        return manifest
```

---

### 3.2 mdgw 升级流程

mdgw 的版本升级相对简单，配置文件结构在不同版本间保持兼容。

| 升级路径 | 配置兼容性 | 操作步骤 |
|----------|-----------|---------|
| 20230609 → 20240722 | 兼容 | 1. 备份旧版本 2. 替换二进制 3. 验证启动 |
| 通用Linux → 麒麟V10 | 兼容 | 1. 检测OS类型 2. 选择对应平台二进制 3. 替换 |

```python
    def upgrade_mdgw(self, new_archive: Path, manifest: BackupManifest) -> bool:
        """mdgw 升级（配置兼容，直接替换二进制）"""
        try:
            # 1. 停止当前网关
            manager = GatewayProcess(self.gateway_type, str(self.gateway_dir))
            manager.stop(force=False, timeout=30)

            # 2. 解压新版本
            with zipfile.ZipFile(new_archive, 'r') as z:
                # 查找二进制文件
                binary_member = None
                for name in z.namelist():
                    if name.endswith('/mdgw') or name == 'mdgw':
                        binary_member = name
                        break

                if not binary_member:
                    raise ValueError("压缩包中未找到 mdgw 二进制文件")

                # 提取二进制
                z.extract(binary_member, self.gateway_dir)
                extracted = self.gateway_dir / binary_member
                if extracted != self.binary_path:
                    shutil.move(str(extracted), str(self.binary_path))
                    # 清理空目录
                    if extracted.parent != self.gateway_dir:
                        extracted.parent.rmdir()

            # 3. 设置权限
            self.binary_path.chmod(self.binary_path.stat().st_mode | 0o111)

            # 4. 启动并验证
            manager.start(timeout=30)
            return True

        except Exception as e:
            logger.error(f"mdgw 升级失败: {e}")
            self.rollback(manifest)
            return False
```

---

### 3.3 tgw 升级流程

tgw 从 20211101 升级到 20240823 涉及**配置架构变更**，需要执行配置迁移。

#### 升级步骤

1. **server_list 剥离**: 从旧版 `config.xml` 的 `<tgw_list>/<tgw>/<server_list>` 提取服务器列表，生成独立的 `server_list.xml`
2. **移除 block_cc_report**: 从 `config.xml` 中删除该配置项
3. **密码变更**: 旧版密码为 `__GWID__`，新版需通过监控界面生成加密密码 `__PASSWORD__`
4. **固定收益平台启用**: 20240823 版本默认启用平台 6

```python
    def migrate_tgw_config(
        self,
        old_config_path: Path,
        new_config_path: Path,
        server_list_path: Path
    ) -> None:
        """
        将 tgw 20211101 配置迁移到 20240823 格式

        主要变更:
        1. 提取 server_list 到独立文件
        2. 移除 block_cc_report
        3. 更新密码占位符
        """
        tree = ET.parse(old_config_path)
        root = tree.getroot()

        # 1. 提取 server_list
        tgw_elem = root.find('.//tgw_list/tgw')
        if tgw_elem is None:
            raise ConfigError("E1002", "config.xml 中未找到 tgw 配置节点")

        server_list = tgw_elem.find('server_list')
        if server_list is not None:
            # 生成 server_list.xml（旧版单组映射为 group no=1）
            sl_root = ET.Element('server_list')
            group = ET.SubElement(sl_root, 'group', no='1')

            for server in server_list.findall('server'):
                group.append(server)

            ET.indent(sl_root, space='  ')
            ET.ElementTree(sl_root).write(
                server_list_path, encoding='UTF-8', xml_declaration=True
            )

            # 从 config.xml 中移除 server_list
            tgw_elem.remove(server_list)
            logger.info(f"已提取 server_list 到 {server_list_path}")

        # 2. 移除 block_cc_report
        block_cc = tgw_elem.find('block_cc_report')
        if block_cc is not None:
            tgw_elem.remove(block_cc)
            logger.info("已移除废弃的 block_cc_report 配置项")

        # 3. 更新密码占位符（提醒用户后续需手动更新为加密密码）
        password = tgw_elem.find('password')
        if password is not None and password.text == '__GWID__':
            password.text = '__PASSWORD__'
            logger.warning(
                "密码占位符已更新为 __PASSWORD__，"
                "请通过网关监控界面生成加密密码后更新配置"
            )

        # 4. 保存新配置
        tree.write(new_config_path, encoding='UTF-8', xml_declaration=True)
        logger.info(f"配置已迁移到 {new_config_path}")

    def upgrade_tgw(self, new_archive: Path, manifest: BackupManifest) -> bool:
        """tgw 升级（含配置迁移）"""
        try:
            # 1. 停止当前网关
            manager = GatewayProcess(self.gateway_type, str(self.gateway_dir))
            manager.stop(force=False, timeout=30)

            # 2. 执行配置迁移
            old_config = manifest.config_backup
            new_config = self.config_path
            server_list = self.server_list_path

            self.migrate_tgw_config(old_config, new_config, server_list)

            # 3. 解压并替换二进制
            with zipfile.ZipFile(new_archive, 'r') as z:
                binary_member = None
                for name in z.namelist():
                    if name.endswith('/tgw') or name == 'tgw':
                        binary_member = name
                        break

                if not binary_member:
                    raise ValueError("压缩包中未找到 tgw 二进制文件")

                z.extract(binary_member, self.gateway_dir)
                extracted = self.gateway_dir / binary_member
                if extracted != self.binary_path:
                    shutil.move(str(extracted), str(self.binary_path))
                    if extracted.parent != self.gateway_dir:
                        extracted.parent.rmdir()

            self.binary_path.chmod(self.binary_path.stat().st_mode | 0o111)

            # 4. 启动并验证
            manager.start(timeout=30)
            return True

        except Exception as e:
            logger.error(f"tgw 升级失败: {e}")
            self.rollback(manifest)
            return False
```

---

### 3.4 回滚机制

```python
    def rollback(self, manifest: BackupManifest) -> bool:
        """
        回滚到备份版本

        步骤:
        1. 停止当前网关
        2. 恢复旧二进制
        3. 恢复旧配置
        4. 启动旧版本
        5. 验证
        """
        try:
            logger.info(f"开始回滚到版本 {manifest.version}")

            # 1. 停止当前网关
            manager = GatewayProcess(self.gateway_type, str(self.gateway_dir))
            manager.stop(force=True, timeout=10)

            # 2. 恢复二进制
            shutil.copy2(manifest.binary_backup, self.binary_path)
            self.binary_path.chmod(self.binary_path.stat().st_mode | 0o111)

            # 3. 恢复配置
            shutil.copy2(manifest.config_backup, self.config_path)

            # 4. 恢复 server_list.xml（如果备份存在）
            if manifest.server_list_backup and manifest.server_list_backup.exists():
                shutil.copy2(manifest.server_list_backup, self.server_list_path)
            elif self.server_list_path.exists():
                # 如果回滚到旧版本但存在 server_list.xml，删除它
                self.server_list_path.unlink()

            # 5. 启动并验证
            if manager.start(timeout=30):
                logger.info(f"回滚成功，当前版本: {manifest.version}")
                return True
            else:
                logger.error("回滚后启动失败")
                return False

        except Exception as e:
            logger.error(f"回滚失败: {e}")
            return False
```

---

## 第4章 启停管理

### 4.1 进程管理策略

- 网关程序**无启动脚本**，直接执行二进制文件
- 进程**工作目录**必须为二进制所在目录（程序在当前目录下查找 `cfg/` 子目录）
- 使用 `subprocess.Popen` 启动，必须设置 `cwd` 参数
- 使用 `start_new_session=True` 创建独立进程组，避免被终端信号影响
- 使用 PID 文件记录进程 ID，便于后续管理
- 使用 `psutil` 进行进程状态监控（提供不依赖 psutil 的回退方案）

---

### 4.2 启动流程

```python
import os
import socket
import subprocess
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GatewayProcess:
    """网关进程管理器"""

    def __init__(self, gateway_type: str, gateway_dir: str):
        self.gateway_type = gateway_type  # "mdgw" 或 "tgw"
        self.gateway_dir = Path(gateway_dir)
        self.binary_path = self.gateway_dir / gateway_type
        self.pid_file = self.gateway_dir / f".{gateway_type}.pid"
        self.monitor_port = 7501 if gateway_type == "mdgw" else 7500
        self.process: Optional[subprocess.Popen] = None

    def start(self, timeout: int = 30) -> bool:
        """
        启动网关进程并等待监控端口就绪

        Args:
            timeout: 等待监控端口就绪的最大秒数

        Returns:
            True: 启动成功
            False: 启动失败
        """
        # 1. 检查是否已在运行
        if self.is_running():
            pid = self.get_pid()
            logger.warning(f"{self.gateway_type} 已在运行, PID={pid}")
            return False

        # 2. 检查配置文件
        config_path = self.gateway_dir / "cfg" / "config.xml"
        if not config_path.exists():
            raise ConfigError("E1001", f"配置文件不存在: {config_path}")

        # 3. 检查二进制
        if not self.binary_path.exists():
            raise BinaryError("E2001", f"二进制文件不存在: {self.binary_path}")
        if not os.access(self.binary_path, os.X_OK):
            raise BinaryError("E2002", f"二进制文件无执行权限: {self.binary_path}")

        # 4. 启动进程
        logger.info(f"启动 {self.gateway_type} ...")
        self.process = subprocess.Popen(
            [f"./{self.gateway_type}"],
            cwd=self.gateway_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # 独立进程组
        )

        # 5. 写入 PID 文件
        with open(self.pid_file, "w") as f:
            f.write(str(self.process.pid))
        logger.info(f"进程已启动, PID={self.process.pid}")

        # 6. 等待监控端口就绪
        if self._wait_for_monitor(timeout):
            logger.info(f"{self.gateway_type} 启动成功, 监控端口 {self.monitor_port} 已就绪")
            return True
        else:
            logger.error(f"{self.gateway_type} 启动超时, 监控端口 {self.monitor_port} 未就绪")
            self.stop(force=True)
            raise ProcessError("E4003", f"启动超时: 监控端口 {self.monitor_port} 未就绪")

    def _wait_for_monitor(self, timeout: int) -> bool:
        """等待监控端口可连接"""
        start = time.time()
        while time.time() - start < timeout:
            if self._check_monitor_port():
                return True
            time.sleep(1)
        return False

    def _check_monitor_port(self) -> bool:
        """检查监控端口是否可连接"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(("127.0.0.1", self.monitor_port))
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False
```

---

### 4.3 停止流程

```python
    def stop(self, force: bool = False, timeout: int = 30) -> bool:
        """
        停止网关进程

        Args:
            force: True=强制终止(SIGKILL), False=优雅关闭(SIGTERM)
            timeout: 等待进程退出的最大秒数

        Returns:
            True: 停止成功或进程已不存在
            False: 停止失败
        """
        pid = self.get_pid()
        if pid is None:
            logger.info(f"{self.gateway_type} 未在运行")
            # 清理残留的 PID 文件
            if self.pid_file.exists():
                self.pid_file.unlink()
            return True

        try:
            # 使用 psutil 管理进程
            proc = self._get_process(pid)
            if proc is None:
                logger.info(f"进程 {pid} 已不存在")
                self._cleanup_pid_file()
                return True

            if force:
                logger.warning(f"强制终止 {self.gateway_type}, PID={pid}")
                proc.kill()  # SIGKILL
            else:
                logger.info(f"优雅关闭 {self.gateway_type}, PID={pid}")
                proc.terminate()  # SIGTERM

            # 等待进程退出
            try:
                proc.wait(timeout=timeout)
                logger.info(f"{self.gateway_type} 已停止, PID={pid}")
            except Exception:
                logger.warning(f"优雅关闭超时, 强制终止 PID={pid}")
                proc.kill()
                proc.wait(timeout=5)

            self._cleanup_pid_file()
            return True

        except Exception as e:
            logger.error(f"停止 {self.gateway_type} 失败: {e}")
            return False

    def _get_process(self, pid: int):
        """获取进程对象（支持 psutil 和回退方案）"""
        try:
            import psutil
            return psutil.Process(pid)
        except ImportError:
            # 回退方案：使用 os.kill 发送信号
            return _FallbackProcess(pid)

    def _cleanup_pid_file(self):
        """清理 PID 文件"""
        if self.pid_file.exists():
            self.pid_file.unlink()


class _FallbackProcess:
    """不依赖 psutil 的进程管理回退类"""

    def __init__(self, pid: int):
        self.pid = pid

    def kill(self):
        import signal
        os.kill(self.pid, signal.SIGKILL)

    def terminate(self):
        import signal
        os.kill(self.pid, signal.SIGTERM)

    def wait(self, timeout: int = None):
        import signal
        start = time.time()
        while True:
            try:
                os.kill(self.pid, 0)  # 检查进程是否存在
            except ProcessLookupError:
                return  # 进程已退出
            if timeout and time.time() - start > timeout:
                raise TimeoutError(f"等待进程 {self.pid} 退出超时")
            time.sleep(0.5)
```

---

### 4.4 状态检查

```python
    def is_running(self) -> bool:
        """检查网关是否正在运行"""
        pid = self.get_pid()
        if pid is None:
            return False
        return self._pid_exists(pid)

    def get_pid(self) -> Optional[int]:
        """获取进程 PID（从 PID 文件或进程名查找）"""
        # 优先从 PID 文件读取
        if self.pid_file.exists():
            try:
                return int(self.pid_file.read_text().strip())
            except ValueError:
                pass

        # 回退：通过进程名查找
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == self.gateway_type:
                    return proc.info['pid']
        except ImportError:
            pass

        return None

    def _pid_exists(self, pid: int) -> bool:
        """检查 PID 是否存在"""
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

    def get_status(self) -> dict:
        """获取网关详细状态"""
        pid = self.get_pid()
        status = {
            'gateway_type': self.gateway_type,
            'running': False,
            'pid': pid,
            'monitor_port': self.monitor_port,
            'monitor_accessible': False,
            'memory_usage_mb': None,
            'cpu_percent': None,
            'uptime_seconds': None,
        }

        if pid and self._pid_exists(pid):
            status['running'] = True
            status['monitor_accessible'] = self._check_monitor_port()

            # 获取资源使用（如果 psutil 可用）
            try:
                import psutil
                proc = psutil.Process(pid)
                status['memory_usage_mb'] = proc.memory_info().rss / (1024 ** 2)
                status['cpu_percent'] = proc.cpu_percent(interval=0.5)
                status['uptime_seconds'] = time.time() - proc.create_time()
            except (ImportError, psutil.NoSuchProcess):
                pass

        return status
```

---

### 4.5 批量管理

```python
import json
from typing import Dict, List


class GatewayManager:
    """多网关实例批量管理器"""

    def __init__(self, config_file: str = "gateway_manager.json"):
        self.config_file = config_file
        self.gateways: Dict[str, GatewayProcess] = {}
        self._load_config()

    def _load_config(self):
        """加载网关配置列表"""
        if not os.path.exists(self.config_file):
            return

        with open(self.config_file) as f:
            config = json.load(f)

        for name, info in config.get("gateways", {}).items():
            self.gateways[name] = GatewayProcess(
                info["type"],
                info["dir"]
            )

    def register(self, name: str, gateway_type: str, gateway_dir: str):
        """注册网关实例"""
        self.gateways[name] = GatewayProcess(gateway_type, gateway_dir)
        self._save_config()

    def _save_config(self):
        """保存网关配置列表"""
        config = {
            "gateways": {
                name: {"type": gp.gateway_type, "dir": str(gp.gateway_dir)}
                for name, gp in self.gateways.items()
            }
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def start_all(self) -> Dict[str, bool]:
        """启动所有网关"""
        results = {}
        for name, gp in self.gateways.items():
            try:
                results[name] = gp.start(timeout=30)
            except Exception as e:
                logger.error(f"启动 {name} 失败: {e}")
                results[name] = False
        return results

    def stop_all(self, force: bool = False) -> Dict[str, bool]:
        """停止所有网关"""
        results = {}
        for name, gp in self.gateways.items():
            results[name] = gp.stop(force=force)
        return results

    def restart_all(self, force: bool = False) -> Dict[str, bool]:
        """重启所有网关"""
        self.stop_all(force=force)
        time.sleep(2)
        return self.start_all()

    def status_all(self) -> Dict[str, dict]:
        """获取所有网关状态"""
        return {name: gp.get_status() for name, gp in self.gateways.items()}

    def start_by_name(self, name: str) -> bool:
        """按名称启动指定网关"""
        if name not in self.gateways:
            raise ValueError(f"未找到网关: {name}")
        return self.gateways[name].start(timeout=30)

    def stop_by_name(self, name: str, force: bool = False) -> bool:
        """按名称停止指定网关"""
        if name not in self.gateways:
            raise ValueError(f"未找到网关: {name}")
        return self.gateways[name].stop(force=force)
```

---

## 第5章 配置文件解析与生成

### 5.1 数据模型定义

```python
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MdgwConfig:
    """行情网关配置数据模型"""
    # 基础配置
    protocol: str = "STEP"           # STEP 或 BINARY
    id: str = ""                     # 网关ID
    type: str = "NETWORK"            # NETWORK 或 LIVE
    password: str = ""               # 密码
    env_id: int = 0                  # 0=生产, 1=期权全真, 2=联网测试
    status_log_interval: int = 180
    user_send_queue_len: int = 100000

    # SSL 认证
    auth_mode: int = 1               # 0=TCP, 1=SSL无证书, 2=SSL文件证书, 3=SSL EKey
    ca_file: str = "ca.crt"
    cert_name: str = ""
    cert_file: str = ""
    private_key_file: str = ""
    private_key_password: str = ""
    ekey_driver_file: str = ""
    ekey_driver_type: str = "PKCS11"

    # 自动清理
    auto_clean_enable: int = 1
    auto_clean_keep_days: int = 14

    # 数据持久化
    data_persistence_server: int = 0
    data_persistence_user: int = 0

    # UDP 特有
    access_mode: str = ""            # TCP 或 UDP
    udp_send_speed: int = 0
    news_path: str = ""

    # 服务端口
    realtime_port: int = 8016
    realtime_interface: str = "0.0.0.0"
    resend_port: int = 8018
    resend_interface: str = "0.0.0.0"

    # 监控服务
    monitor_port: int = 7501
    monitor_password: str = "password"
    monitor_allowed_address: str = ""

    # 通道配置
    line_types: List[dict] = field(default_factory=list)
    admin_lines: List[dict] = field(default_factory=list)
    resend_lines: List[dict] = field(default_factory=list)
    user_channels: List[str] = field(default_factory=list)
    blocked_channels: List[str] = field(default_factory=list)


@dataclass
class TgwConfig:
    """交易网关配置数据模型"""
    # 基础配置
    protocol: str = "BINARY"
    id: str = ""
    env_id: int = 0                  # 0=生产, 1=期权全真, 2=联网测试
    password: str = ""

    # SSL 认证
    auth_mode: int = 1
    ca_file: str = "ca.crt"
    cert_name: str = ""
    cert_file: str = ""
    private_key_file: str = ""
    private_key_password: str = ""
    ekey_driver_file: str = ""
    ekey_driver_type: str = "PKCS11"
    is_aggregation: int = 0

    # 自动清理
    auto_clean_enable: int = 0
    auto_clean_keep_days: int = 14

    # 数据持久化
    data_persistence_server: int = 0
    data_persistence_user: int = 0

    # 监控服务
    monitor_port: int = 7500
    monitor_password: str = "password"
    monitor_allowed_address: str = ""

    # 接入用户
    access_password: str = ""
    allowed_addresses: str = ""
    platforms: List[dict] = field(default_factory=list)

    # 服务器分组 (20240823+)
    server_groups: List[dict] = field(default_factory=list)
```

---

### 5.2 XML 解析器

```python
import xml.etree.ElementTree as ET


class MdgwConfigParser:
    """mdgw 配置文件解析器"""

    @staticmethod
    def parse(config_path: str) -> MdgwConfig:
        """解析 mdgw config.xml"""
        tree = ET.parse(config_path)
        root = tree.getroot()
        config = MdgwConfig()

        # 基础字段
        config.protocol = root.findtext("protocol", "STEP")
        config.id = root.findtext("id", "")
        config.type = root.findtext("type", "NETWORK")
        config.password = root.findtext("password", "")
        config.env_id = int(root.findtext("env_id", "0"))
        config.status_log_interval = int(root.findtext("status_log_interval", "180"))
        config.user_send_queue_len = int(root.findtext("user_send_queue_len", "100000"))

        # SSL
        config.auth_mode = int(root.findtext("auth_mode", "1"))
        config.ca_file = root.findtext("ca_file", "ca.crt")
        config.cert_name = root.findtext("cert_name", "")
        config.cert_file = root.findtext("cert_file", "")
        config.private_key_file = root.findtext("private_key_file", "")
        config.private_key_password = root.findtext("private_key_password", "")
        config.ekey_driver_file = root.findtext("ekey_driver_file", "")
        config.ekey_driver_type = root.findtext("ekey_driver_type", "PKCS11")

        # auto_clean
        ac = root.find("auto_clean")
        if ac is not None:
            config.auto_clean_enable = int(ac.findtext("enable", "1"))
            config.auto_clean_keep_days = int(ac.findtext("keep_days", "14"))

        # data_persistence
        dp = root.find("data_persistence")
        if dp is not None:
            config.data_persistence_server = int(dp.findtext("server_enable", "0"))
            config.data_persistence_user = int(dp.findtext("user_enable", "0"))

        # UDP 特有
        config.access_mode = root.findtext("access_mode", "")
        config.udp_send_speed = int(root.findtext("udp_send_speed", "0"))
        config.news_path = root.findtext("news_path", "")

        # 监控服务
        ms = root.find("monitor_service")
        if ms is not None:
            config.monitor_port = int(ms.findtext("port", "7501"))
            config.monitor_password = ms.findtext("password", "password")
            config.monitor_allowed_address = ms.findtext("allowed_address", "")

        # 实时服务
        rs = root.find(".//access_user/realtime_service_list/realtime_service")
        if rs is not None:
            config.realtime_port = int(rs.findtext("port", "8016"))
            config.realtime_interface = rs.findtext("interface", "0.0.0.0")

        # 重传服务
        resend = root.find(".//access_user/resend_service")
        if resend is not None:
            config.resend_port = int(resend.findtext("port", "8018"))

        # 通道类型
        lt_list = root.find(".//comm_server/line_type_list")
        if lt_list is not None:
            config.line_types = [
                {"type": lt.findtext("type", ""), "description": lt.findtext("description", "")}
                for lt in lt_list.findall("line_type")
            ]

        return config


class TgwConfigParser:
    """tgw 配置文件解析器"""

    @staticmethod
    def parse(config_path: str, server_list_path: Optional[str] = None) -> TgwConfig:
        """解析 tgw config.xml（可选解析独立的 server_list.xml）"""
        tree = ET.parse(config_path)
        root = tree.getroot()
        config = TgwConfig()

        # 基础字段
        config.protocol = root.findtext("protocol", "BINARY")
        config.id = root.findtext("id", "")
        config.env_id = int(root.findtext("env_id", "0"))

        # tgw 详细配置
        tgw_elem = root.find(".//tgw_list/tgw")
        if tgw_elem is not None:
            config.password = tgw_elem.findtext("password", "")
            config.auth_mode = int(tgw_elem.findtext("auth_mode", "1"))
            config.ca_file = tgw_elem.findtext("ca_file", "ca.crt")
            config.is_aggregation = int(tgw_elem.findtext("is_aggregation", "0"))
            config.ekey_driver_file = tgw_elem.findtext("ekey_driver_file", "")
            config.ekey_driver_type = tgw_elem.findtext("ekey_driver_type", "PKCS11")

        # auto_clean
        ac = root.find("auto_clean")
        if ac is not None:
            config.auto_clean_enable = int(ac.findtext("enable", "0"))
            config.auto_clean_keep_days = int(ac.findtext("keep_days", "14"))

        # data_persistence
        dp = root.find("data_persistence")
        if dp is not None:
            config.data_persistence_server = int(dp.findtext("server_enable", "0"))
            config.data_persistence_user = int(dp.findtext("user_enable", "0"))

        # 接入用户
        au = root.find("access_user")
        if au is not None:
            config.access_password = au.findtext("password", "")
            config.allowed_addresses = au.findtext("allowed_addresses", "")

            # 平台列表
            pl = au.find("platform_list")
            if pl is not None:
                config.platforms = [
                    {
                        "id": int(p.findtext("id", "0")),
                        "description": p.findtext("description", ""),
                        "interface": p.findtext("interface", "0.0.0.0"),
                        "port": int(p.findtext("port", "0"))
                    }
                    for p in pl.findall("platform")
                ]

        # 监控服务
        ms = root.find("monitor_service")
        if ms is not None:
            config.monitor_port = int(ms.findtext("port", "7500"))
            config.monitor_password = ms.findtext("password", "password")
            config.monitor_allowed_address = ms.findtext("allowed_address", "")

        # 解析独立的 server_list.xml
        if server_list_path and os.path.exists(server_list_path):
            config.server_groups = TgwConfigParser.parse_server_list(server_list_path)
        else:
            # 尝试从 config.xml 内嵌的 server_list 解析（旧版本）
            sl = root.find(".//tgw_list/tgw/server_list")
            if sl is not None:
                config.server_groups = [{
                    "no": "1",
                    "servers": [
                        {
                            "description": s.findtext("description", ""),
                            "address": s.findtext("address", ""),
                            "port": int(s.findtext("port", "7019")),
                            "knock_offset_time": int(s.findtext("knock_offset_time", "0"))
                        }
                        for s in sl.findall("server")
                    ]
                }]

        return config

    @staticmethod
    def parse_server_list(server_list_path: str) -> List[dict]:
        """解析独立的 server_list.xml"""
        tree = ET.parse(server_list_path)
        root = tree.getroot()
        groups = []
        for group in root.findall("group"):
            g = {
                "no": group.get("no", ""),
                "servers": [
                    {
                        "description": s.findtext("description", ""),
                        "address": s.findtext("address", ""),
                        "port": int(s.findtext("port", "7019")),
                        "knock_offset_time": int(s.findtext("knock_offset_time", "0"))
                    }
                    for s in group.findall("server")
                ]
            }
            groups.append(g)
        return groups
```

---

### 5.3 配置校验器

```python
class ConfigValidator:
    """配置校验器"""

    @staticmethod
    def validate_mdgw(config: MdgwConfig) -> List[tuple]:
        """
        校验 mdgw 配置

        Returns:
            List[(level, message)]，level: ERROR / WARNING
        """
        errors = []

        if not config.id:
            errors.append(("ERROR", "网关ID (id) 不能为空"))

        if config.protocol not in ("STEP", "BINARY"):
            errors.append(("ERROR", f"不支持的协议: {config.protocol}，必须是 STEP 或 BINARY"))

        if config.type not in ("NETWORK", "LIVE"):
            errors.append(("ERROR", f"无效的网关类型: {config.type}，必须是 NETWORK 或 LIVE"))

        if config.env_id not in (0, 1, 2):
            errors.append(("ERROR", f"无效的环境号: {config.env_id}，必须是 0(生产)/1(期权全真)/2(联网测试)"))

        if config.auth_mode not in (0, 1, 2, 3):
            errors.append(("ERROR", f"无效的认证模式: {config.auth_mode}，必须是 0-3"))

        if config.auth_mode in (2, 3) and not config.ca_file:
            errors.append(("WARNING", "SSL 证书模式需要配置 CA 证书文件 (ca_file)"))

        if config.type == "NETWORK" and config.realtime_port == config.resend_port:
            errors.append(("ERROR", f"实时端口 ({config.realtime_port}) 与重传端口 ({config.resend_port}) 不能相同"))

        if config.access_mode == "UDP" and config.protocol != "BINARY":
            errors.append(("ERROR", "UDP 接入模式只支持 BINARY 协议"))

        return errors

    @staticmethod
    def validate_tgw(config: TgwConfig, version: str = "20240823") -> List[tuple]:
        """校验 tgw 配置"""
        errors = []

        if not config.id:
            errors.append(("ERROR", "网关ID (id) 不能为空"))

        if config.env_id not in (0, 1, 2):
            errors.append(("ERROR", f"无效的环境号: {config.env_id}"))

        if config.auth_mode not in (0, 1, 2, 3):
            errors.append(("ERROR", f"无效的认证模式: {config.auth_mode}"))

        if version == "20240823" and not config.server_groups:
            errors.append(("ERROR", "20240823 版本需要配置 server_list.xml"))

        # 检查平台端口冲突
        ports_used = set()
        for p in config.platforms:
            if p["port"] in ports_used:
                errors.append(("ERROR", f"平台端口冲突: {p['port']}"))
            ports_used.add(p["port"])

        # 检查 server_list 中的端口
        for g in config.server_groups:
            for s in g.get("servers", []):
                if s.get("port", 0) <= 0 or s.get("port", 0) > 65535:
                    errors.append(("ERROR", f"无效的服务器端口: {s.get('port')}"))

        return errors
```

---

### 5.4 配置迁移工具

```python
class ConfigMigrator:
    """配置迁移工具（tgw 20211101 -> 20240823）"""

    @staticmethod
    def migrate_tgw(
        old_config_path: str,
        new_config_path: str,
        server_list_path: str
    ) -> List[str]:
        """
        执行 tgw 配置迁移

        Returns:
            迁移日志列表
        """
        logs = []
        tree = ET.parse(old_config_path)
        root = tree.getroot()

        tgw_elem = root.find('.//tgw_list/tgw')
        if tgw_elem is None:
            raise ConfigError("E1002", "config.xml 中未找到 tgw 配置节点")

        # 1. 提取 server_list
        server_list = tgw_elem.find('server_list')
        if server_list is not None:
            sl_root = ET.Element('server_list')
            group = ET.SubElement(sl_root, 'group', no='1')
            for server in server_list.findall('server'):
                group.append(server)
            ET.indent(sl_root, space='  ')
            ET.ElementTree(sl_root).write(
                server_list_path, encoding='UTF-8', xml_declaration=True
            )
            tgw_elem.remove(server_list)
            logs.append(f"已提取 server_list 到 {server_list_path}")
        else:
            logs.append("警告: 旧配置中未找到 server_list 节点")

        # 2. 移除 block_cc_report
        block_cc = tgw_elem.find('block_cc_report')
        if block_cc is not None:
            tgw_elem.remove(block_cc)
            logs.append("已移除废弃的 block_cc_report 配置项")

        # 3. 更新密码占位符
        password = tgw_elem.find('password')
        if password is not None:
            old_pwd = password.text
            if old_pwd == '__GWID__':
                password.text = '__PASSWORD__'
                logs.append("密码占位符已更新为 __PASSWORD__（需手动替换为加密密码）")

        # 4. 保存新配置
        tree.write(new_config_path, encoding='UTF-8', xml_declaration=True)
        logs.append(f"配置已迁移到 {new_config_path}")

        return logs
```

---

## 第6章 错误处理与日志

### 6.1 错误分类体系

| 错误码 | 类别 | 说明 | 处理策略 |
|--------|------|------|---------|
| E1001 | CONFIG_ERROR | 配置文件不存在 | 终止操作，提示用户创建配置 |
| E1002 | CONFIG_PARSE_ERROR | XML 解析失败 | 终止操作，输出解析错误位置 |
| E1003 | CONFIG_VALIDATE_ERROR | 配置校验失败 | 终止操作，列出所有校验错误 |
| E2001 | BINARY_ERROR | 二进制文件不存在 | 终止操作 |
| E2002 | BINARY_PERMISSION | 二进制无执行权限 | 尝试 chmod +x，失败则终止 |
| E2003 | DEP_MISSING | 动态库依赖缺失 | 列出缺失库，终止操作 |
| E3001 | PORT_IN_USE | 端口被占用 | 报告占用进程，终止操作 |
| E4001 | PROCESS_ALREADY_RUNNING | 进程已在运行 | 提示用户，跳过或终止旧进程 |
| E4002 | PROCESS_START_FAILED | 启动失败（退出码非0） | 收集 stderr，分析原因 |
| E4003 | PROCESS_START_TIMEOUT | 启动超时（监控端口未就绪） | 自动回滚 |
| E5001 | MONITOR_UNREACHABLE | 监控端口不可达 | 重试3次，告警 |
| E6001 | UPGRADE_MIGRATE_ERROR | 配置迁移失败 | 自动回滚 |
| E6002 | UPGRADE_VERIFY_ERROR | 升级验证失败 | 自动回滚 |

---

### 6.2 自定义异常类

```python
class GatewayError(Exception):
    """网关管理基础异常"""

    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


class ConfigError(GatewayError):
    """配置相关错误 (E1001-E1003)"""
    pass


class BinaryError(GatewayError):
    """二进制文件相关错误 (E2001-E2003)"""
    pass


class ProcessError(GatewayError):
    """进程管理相关错误 (E4001-E4003)"""
    pass


class UpgradeError(GatewayError):
    """升级相关错误 (E6001-E6002)"""
    pass
```

---

### 6.3 日志配置

```python
import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging(log_dir: str, gateway_name: str) -> logging.Logger:
    """
    配置网关管理工具的日志系统

    Args:
        log_dir: 日志目录
        gateway_name: 网关名称（用于日志文件名）

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(gateway_name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台输出（INFO 级别）
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(console)

    # 文件输出（DEBUG 级别，按天轮转，保留30天）
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{gateway_name}_manager.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [%(funcName)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    return logger
```

---

### 6.4 操作审计日志

```python
import json
from datetime import datetime
from typing import Optional


class AuditLogger:
    """操作审计日志记录器"""

    def __init__(self, audit_log_path: str):
        self.log_path = audit_log_path
        # 确保日志目录存在
        os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)

    def log(
        self,
        operation: str,           # deploy / start / stop / upgrade / rollback / status
        gateway: str,             # mdgw / tgw
        params: dict,
        result: str,              # success / failure
        details: str = "",
        user: str = "admin"
    ):
        """记录操作审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "operation": operation,
            "gateway": gateway,
            "params": params,
            "result": result,
            "details": details
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def query(
        self,
        gateway: Optional[str] = None,
        operation: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[dict]:
        """查询审计日志"""
        results = []
        if not os.path.exists(self.log_path):
            return results

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(entry["timestamp"])

                    if gateway and entry["gateway"] != gateway:
                        continue
                    if operation and entry["operation"] != operation:
                        continue
                    if start_time and entry_time < start_time:
                        continue
                    if end_time and entry_time > end_time:
                        continue

                    results.append(entry)
                    if len(results) >= limit:
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

        return results
```

---

## 第7章 完整使用示例

### 7.1 部署 mdgw 示例

```python
#!/usr/bin/env python3
"""mdgw 全新部署示例"""

from pathlib import Path


def deploy_mdgw_example():
    # 1. 初始化部署器
    deployer = GatewayDeployer(
        gateway_type="mdgw",
        install_dir=Path("/opt/gateway")
    )

    # 2. 定义配置参数
    config_params = {
        "gwid": "MDGW001",
        "env_id": 0,              # 生产环境
        "level": 2,               # Level2
        "access_mode": "TCP",     # TCP 接入
        "line_type": "地面",
        "local_ip": "192.168.1.100",
        "overrides": {
            "auth_mode": 1,       # SSL 无证书
            "auto_clean/enable": 1,
            "auto_clean/keep_days": 14
        }
    }

    # 3. 执行部署
    result = deployer.deploy(
        archive_path=Path("/opt/archives/mdgw_20240722_linux.zip"),
        config_params=config_params
    )

    if result.success:
        print(f"部署成功: {result.config_path}")
    else:
        print(f"部署失败: {result.message}")


if __name__ == "__main__":
    deploy_mdgw_example()
```

---

### 7.2 部署 tgw 示例

```python
#!/usr/bin/env python3
"""tgw 全新部署示例（20240823 版本）"""

from pathlib import Path


def deploy_tgw_example():
    deployer = GatewayDeployer(
        gateway_type="tgw",
        install_dir=Path("/opt/gateway")
    )

    # 配置参数
    config_params = {
        "gwid": "TGW001",
        "password": "__PASSWORD__",  # 需后续通过监控界面替换为加密密码
        "env_id": 0,
        "overrides": {
            "auto_clean/enable": 1
        }
    }

    # 服务器分组配置（server_list.xml）
    server_list_groups = [
        {
            "no": "1",
            "servers": [
                {
                    "description": "主用服务器地址",
                    "address": "10.0.1.1",
                    "port": 7019,
                    "knock_offset_time": 0
                },
                {
                    "description": "备用服务器地址",
                    "address": "10.0.1.2",
                    "port": 7019,
                    "knock_offset_time": 0
                }
            ]
        }
    ]

    result = deployer.deploy(
        archive_path=Path("/opt/archives/tgw_20240823_linux.zip"),
        config_params=config_params,
        server_list_groups=server_list_groups
    )

    if result.success:
        print(f"部署成功")
        print(f"  config.xml: {result.config_path}")
        print(f"  server_list.xml: {result.server_list_path}")
    else:
        print(f"部署失败: {result.message}")


if __name__ == "__main__":
    deploy_tgw_example()
```

---

### 7.3 升级 tgw 示例

```python
#!/usr/bin/env python3
"""tgw 升级示例（20211101 -> 20240823）"""

from pathlib import Path


def upgrade_tgw_example():
    gateway_dir = Path("/opt/gateway/tgw")
    backup_dir = Path("/opt/gateway/backup")
    new_archive = Path("/opt/archives/tgw_20240823_linux.zip")

    # 1. 初始化升级器
    upgrader = GatewayUpgrader(
        gateway_type="tgw",
        gateway_dir=gateway_dir,
        backup_dir=backup_dir
    )

    # 2. 检测当前版本
    current_version = upgrader.detect_current_version()
    print(f"当前版本: {current_version}")

    # 3. 备份
    manifest = upgrader.backup()
    print(f"已备份到: {manifest.binary_backup.parent}")

    # 4. 执行升级
    success = upgrader.upgrade_tgw(new_archive, manifest)

    if success:
        print("升级成功")
    else:
        print("升级失败，已自动回滚")


if __name__ == "__main__":
    upgrade_tgw_example()
```

---

### 7.4 日常启停示例

```python
#!/usr/bin/env python3
"""网关日常启停管理示例"""


def daily_operations_example():
    # 初始化管理器
    manager = GatewayManager("gateway_manager.json")

    # 注册网关实例
    manager.register("mdgw_prod", "mdgw", "/opt/gateway/mdgw")
    manager.register("tgw_prod", "tgw", "/opt/gateway/tgw")

    # 启动所有网关
    print("=== 启动所有网关 ===")
    results = manager.start_all()
    for name, ok in results.items():
        print(f"  {name}: {'成功' if ok else '失败'}")

    # 查看状态
    print("\n=== 网关状态 ===")
    statuses = manager.status_all()
    for name, status in statuses.items():
        print(f"  {name}:")
        print(f"    运行中: {status['running']}")
        print(f"    PID: {status['pid']}")
        print(f"    监控端口: {'可达' if status['monitor_accessible'] else '不可达'}")
        if status['memory_usage_mb']:
            print(f"    内存: {status['memory_usage_mb']:.1f} MB")
        if status['uptime_seconds']:
            print(f"    运行时长: {status['uptime_seconds']:.0f} 秒")

    # 停止指定网关
    print("\n=== 停止 tgw_prod ===")
    manager.stop_by_name("tgw_prod", force=False)

    # 重启指定网关
    print("\n=== 重启 mdgw_prod ===")
    manager.stop_by_name("mdgw_prod", force=False)
    manager.start_by_name("mdgw_prod")


if __name__ == "__main__":
    daily_operations_example()
```

---

### 7.5 CLI 命令行工具

```python
#!/usr/bin/env python3
"""网关管理 CLI 工具"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="深交所网关管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s deploy --type mdgw --archive ./mdgw_20240722_linux.zip --gwid MDGW001
  %(prog)s start --name mdgw_prod
  %(prog)s stop --name tgw_prod --force
  %(prog)s status --all
  %(prog)s upgrade --name tgw_prod --archive ./tgw_20240823_linux.zip
  %(prog)s rollback --name tgw_prod --backup 20240607_120000
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # deploy 命令
    deploy_parser = subparsers.add_parser("deploy", help="部署新网关")
    deploy_parser.add_argument("--type", required=True, choices=["mdgw", "tgw"])
    deploy_parser.add_argument("--archive", required=True, help="网关 zip 包路径")
    deploy_parser.add_argument("--gwid", required=True, help="网关ID")
    deploy_parser.add_argument("--env", type=int, default=0, choices=[0, 1, 2])
    deploy_parser.add_argument("--dir", default="/opt/gateway", help="安装目录")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动网关")
    start_parser.add_argument("--name", required=True, help="网关实例名称")

    # stop 命令
    stop_parser = subparsers.add_parser("stop", help="停止网关")
    stop_parser.add_argument("--name", required=True, help="网关实例名称")
    stop_parser.add_argument("--force", action="store_true", help="强制终止")

    # restart 命令
    restart_parser = subparsers.add_parser("restart", help="重启网关")
    restart_parser.add_argument("--name", required=True, help="网关实例名称")
    restart_parser.add_argument("--force", action="store_true", help="强制重启")

    # status 命令
    status_parser = subparsers.add_parser("status", help="查看网关状态")
    status_parser.add_argument("--name", help="网关实例名称")
    status_parser.add_argument("--all", action="store_true", help="查看所有网关")

    # upgrade 命令
    upgrade_parser = subparsers.add_parser("upgrade", help="升级网关")
    upgrade_parser.add_argument("--name", required=True, help="网关实例名称")
    upgrade_parser.add_argument("--archive", required=True, help="新版本 zip 包路径")

    # rollback 命令
    rollback_parser = subparsers.add_parser("rollback", help="回滚网关")
    rollback_parser.add_argument("--name", required=True, help="网关实例名称")
    rollback_parser.add_argument("--backup", required=True, help="备份时间戳")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 初始化管理器
    manager = GatewayManager()

    if args.command == "deploy":
        deployer = GatewayDeployer(args.type, Path(args.dir))
        config_params = {"gwid": args.gwid, "env_id": args.env}
        result = deployer.deploy(Path(args.archive), config_params)
        print(json.dumps({"success": result.success, "message": result.message}, indent=2))

    elif args.command == "start":
        ok = manager.start_by_name(args.name)
        print(f"启动 {'成功' if ok else '失败'}")

    elif args.command == "stop":
        ok = manager.stop_by_name(args.name, force=args.force)
        print(f"停止 {'成功' if ok else '失败'}")

    elif args.command == "restart":
        manager.stop_by_name(args.name, force=args.force)
        ok = manager.start_by_name(args.name)
        print(f"重启 {'成功' if ok else '失败'}")

    elif args.command == "status":
        if args.all:
            statuses = manager.status_all()
        elif args.name:
            gp = manager.gateways.get(args.name)
            statuses = {args.name: gp.get_status() if gp else {}}
        else:
            parser.error("--name 或 --all 必须指定一个")
            return
        print(json.dumps(statuses, indent=2, default=str))

    elif args.command == "upgrade":
        gp = manager.gateways.get(args.name)
        if not gp:
            print(f"未找到网关: {args.name}")
            sys.exit(1)
        upgrader = GatewayUpgrader(
            gp.gateway_type, gp.gateway_dir,
            gp.gateway_dir.parent / "backup"
        )
        manifest = upgrader.backup()
        ok = upgrader.upgrade_tgw(Path(args.archive), manifest)
        print(f"升级 {'成功' if ok else '失败'}")

    elif args.command == "rollback":
        gp = manager.gateways.get(args.name)
        if not gp:
            print(f"未找到网关: {args.name}")
            sys.exit(1)
        upgrader = GatewayUpgrader(
            gp.gateway_type, gp.gateway_dir,
            gp.gateway_dir.parent / "backup"
        )
        # 加载备份清单
        manifest_path = upgrader.backup_dir / f"{gp.gateway_type}_{args.backup}" / "manifest.json"
        with open(manifest_path) as f:
            data = json.load(f)
        manifest = BackupManifest(**data)
        ok = upgrader.rollback(manifest)
        print(f"回滚 {'成功' if ok else '失败'}")


if __name__ == "__main__":
    main()
```

---

## 附录 A: 文件依赖关系

```
gateway_manager/
├── __init__.py
├── deployer.py          # GatewayDeployer, MdgwTemplateSelector, ConfigGenerator
├── process.py           # GatewayProcess, _FallbackProcess
├── manager.py           # GatewayManager
├── upgrader.py          # GatewayUpgrader, ConfigMigrator
├── config_parser.py     # MdgwConfigParser, TgwConfigParser, ConfigValidator
├── checker.py           # PreflightChecker, CheckResult
├── exceptions.py        # GatewayError, ConfigError, BinaryError, ProcessError, UpgradeError
├── logger.py            # setup_logging, AuditLogger
└── cli.py               # main() CLI 入口
```

## 附录 B: 第三方依赖

| 包名 | 版本 | 用途 | 是否必需 |
|------|------|------|---------|
| psutil | >=5.8 | 进程监控、资源统计 | 否（有回退方案） |

其余均使用 Python 标准库。
