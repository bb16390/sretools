# 验证删除 worker/metrics 目录任务的 checklist

- [x] worker/main.py 中不再有对 worker.metrics 模块的导入
- [x] worker/main.py 中不再有对 MetricConverter 的初始化
- [x] worker/main.py 中不再注册 MetricConverterTask
- [x] /workspace/worker/scheduler/tasks/metric_converter_task.py 文件已删除
- [x] tasks/__init__.py 中不再导出 MetricConverterTask
- [x] /workspace/worker/metrics 目录已完全删除
- [x] 项目中没有其他对 worker.metrics 的引用
- [x] worker/README.md 已更新，移除了对 metrics 模块的描述
- [x] 项目可以正常导入，没有 ImportError（注：grpc 模块缺失与本次任务无关）
