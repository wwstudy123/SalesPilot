"""SalesPilot 统一工具层（MCP Server）骨架。

M0 阶段仅提供健康检查端点；M4 起逐步落 10 个工具
（read 7 + write 3）与治理机制（权限闸门/熔断/幂等/缓存/审计）。
"""
