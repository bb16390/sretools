"""master/gateway: 网关控制模块。

本模块在 Master 端提供证券交易所网关（行情 mdgw / 交易 tgw）的统一控制能力：
- deploy / start / stop / restart / upgrade / rollback / status / preflight
- 首期实现：深交所(SZSE) mdgw + tgw
- 预留实现：上交所(SSE) mdgw + tgw、北交所(BJSE) mdgw + tgw
- 可扩展：新增交易所只需在 controllers/ 目录下新增一个文件，并通过
  `@registry.register(exchange, kind)` 装饰器注册，无需修改 core / api / admin。
"""
