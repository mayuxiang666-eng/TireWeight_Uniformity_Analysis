# -*- coding: utf-8 -*-
"""
API 路由控制层 (API Routing Layer)
负责提取 HTTP 入参、参数校验、调用业务服务、格式化返回响应
"""
from backend.routers import system, articles, machines, cgrs, trend

__all__ = ["system", "articles", "machines", "cgrs", "trend"]
