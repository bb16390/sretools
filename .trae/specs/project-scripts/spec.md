# 项目启停与部署脚本规格

## Why
项目包含 master 和 worker 两个独立服务，需要统一的启停脚本和部署脚本，以便于运维管理和自动化部署。

## What Changes
- 新增项目根目录下的启停脚本 `scripts/start.sh` 和 `scripts/stop.sh`
- 新增部署配置向导脚本 `scripts/deploy.sh`
- 支持单独启动/停止 master 或 worker，也支持按顺序启动/停止两者
- 部署脚本提供交互式配置向导，支持选择部署 master、worker 或同时部署两者

## Impact
- 新增脚本：`scripts/start.sh`、`scripts/stop.sh`、`scripts/deploy.sh`
- 配置文件：`master/.env`（部署时生成）、`worker/.env`（部署时生成）

## ADDED Requirements

### Requirement: 启停脚本
系统 SHALL 提供以下启停脚本功能：

#### Scenario: 启动 master 服务
- **WHEN** 执行 `scripts/start.sh master`
- **THEN** 在 master 目录下启动 master 服务（FastAPI + gRPC）

#### Scenario: 启动 worker 服务
- **WHEN** 执行 `scripts/start.sh worker`
- **THEN** 在 worker 目录下启动 worker 服务

#### Scenario: 启动所有服务
- **WHEN** 执行 `scripts/start.sh all`
- **THEN** 先启动 master 服务，等待就绪后启动 worker 服务

#### Scenario: 停止 master 服务
- **WHEN** 执行 `scripts/stop.sh master`
- **THEN** 停止 master 服务进程

#### Scenario: 停止 worker 服务
- **WHEN** 执行 `scripts/stop.sh worker`
- **THEN** 停止 worker 服务进程

#### Scenario: 停止所有服务
- **WHEN** 执行 `scripts/stop.sh all`
- **THEN** 先停止 worker 服务，再停止 master 服务

### Requirement: 部署脚本
系统 SHALL 提供交互式部署配置向导：

#### Scenario: 部署 master
- **WHEN** 执行 `scripts/deploy.sh` 并选择部署 master
- **THEN** 生成 `master/.env` 配置文件，包含数据库连接、服务端口等配置项

#### Scenario: 部署 worker
- **WHEN** 执行 `scripts/deploy.sh` 并选择部署 worker
- **THEN** 生成 `worker/.env` 配置文件，包含 master 连接地址、gRPC 配置等配置项

#### Scenario: 同时部署 master 和 worker
- **WHEN** 执行 `scripts/deploy.sh` 并选择同时部署
- **THEN** 生成 `master/.env` 和 `worker/.env` 两个配置文件

### Requirement: 配置项 - Master
Master 部署配置向导 SHALL 收集以下配置项：
- 数据库连接 URL（支持 SQLite/PostgreSQL）
- 服务监听地址和端口
- 日志级别
- 秘钥（secret_key）

### Requirement: 配置项 - Worker
Worker 部署配置向导 SHALL 收集以下配置项：
- Master 服务地址（gRPC 端口）
- Worker ID
- 日志级别
- 日志收集间隔
- 指标收集间隔

## MODIFIED Requirements

## REMOVED Requirements
