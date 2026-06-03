# Worker HTTP Request Handler Spec

## Why
在worker环境下，需要一个统一的HTTP请求处理模块，支持对不同HTTP地址配置不同的响应处理函数，同时确保HTTP客户端只进行一次实例化以提高性能。

## What Changes
- 在 `worker/` 目录下创建 `http_client/` 子模块
- 实现单例模式的 `HTTPClient` 类，统一管理aiohttp会话
- 支持为每个HTTP地址注册自定义的响应处理函数
- 提供简洁的API进行HTTP请求

## Impact
- 新增代码: `worker/http_client/`
- 依赖: aiohttp

## ADDED Requirements

### Requirement: HTTPClient 单例模式
系统 SHALL 提供一个HTTP客户端单例类，用于管理所有HTTP请求。aiohttp.ClientSession只应实例化一次并被复用。

### Requirement: 响应处理函数注册
系统 SHALL 支持为每个HTTP地址注册自定义的响应处理函数，函数签名应为 `async def handler(response: aiohttp.ClientResponse) -> Any`。

### Requirement: 统一的请求方法
系统 SHALL 提供 `get`, `post`, `put`, `delete` 等标准HTTP方法，参数包括url和可选的data/json。

### Requirement: 处理函数可选
如果某个HTTP地址没有注册处理函数，则返回原始响应对象。

## MODIFIED Requirements
无

## REMOVED Requirements
无

## API Design

```python
class HTTPClient:
    """单例HTTP客户端"""
    
    @classmethod
    def get_instance(cls) -> "HTTPClient":
        """获取单例实例"""
        
    def register_handler(self, url_pattern: str, handler: Callable):
        """注册URL对应的处理函数"""
        
    async def get(self, url: str, **kwargs) -> Any:
        """GET请求"""
        
    async def post(self, url: str, **kwargs) -> Any:
        """POST请求"""
        
    async def put(self, url: str, **kwargs) -> Any:
        """PUT请求"""
        
    async def delete(self, url: str, **kwargs) -> Any:
        """DELETE请求"""
        
    async def close(self):
        """关闭客户端"""
```

## Directory Structure

```
worker/http_client/
├── __init__.py
└── client.py
```
