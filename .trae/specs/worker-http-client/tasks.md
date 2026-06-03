# Tasks

- [ ] Task 1: 创建 http_client 模块目录和 __init__.py
  - [ ] 创建目录 `worker/http_client/`
  - [ ] 创建 `__init__.py` 导出 HTTPClient 类

- [ ] Task 2: 实现 HTTPClient 单例类
  - [ ] 实现 `get_instance()` 类方法实现单例
  - [ ] 初始化 aiohttp.ClientSession
  - [ ] 实现 URL 处理函数注册机制 `register_handler()`
  - [ ] 实现 `get/post/put/delete` 请求方法
  - [ ] 实现 `close()` 方法关闭session

- [ ] Task 3: 创建示例代码和使用说明
  - [ ] 在 `__init__.py` 中添加使用示例作为注释
