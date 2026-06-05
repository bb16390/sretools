# Tasks

- [x] Task 1: 创建启停脚本目录和 start.sh 启停脚本
  - [x] SubTask 1.1: 创建 scripts 目录
  - [x] SubTask 1.2: 实现 start.sh 启停脚本，支持 master/worker/all 参数

- [x] Task 2: 实现 stop.sh 停止脚本
  - [x] SubTask 2.1: 实现 stop.sh，支持 master/worker/all 参数
  - [x] SubTask 2.2: 支持优雅停止服务进程

- [x] Task 3: 创建 deploy.sh 部署配置向导脚本
  - [x] SubTask 3.1: 实现交互式配置向导
  - [x] SubTask 3.2: 支持选择部署 master/worker/all
  - [x] SubTask 3.3: 生成 master/.env 配置文件
  - [x] SubTask 3.4: 生成 worker/.env 配置文件

- [x] Task 4: 验证脚本可执行权限
  - [x] SubTask 4.1: 设置脚本可执行权限

# Task Dependencies
- Task 2 依赖 Task 1（先有 start.sh 后有 stop.sh）
- Task 3 独立于 Task 1 和 Task 2，可并行开发