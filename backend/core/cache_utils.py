# -*- coding: utf-8 -*-
"""
通用内存 TTL 缓存工具模块 (供各服务共用，避免服务间横向耦合)
"""
import time

_param_recommend_cache: dict = {}
_RECOMMEND_CACHE_TTL = 600  # 10 分钟


def recommend_cache_key(article: str, indicator: str, target_date: str) -> str:
    """生成参数推荐缓存键"""
    return f"{article}|{indicator}|{target_date}"


def recommend_cache_get(key: str):
    """获取尚未过期的缓存值"""
    entry = _param_recommend_cache.get(key)
    if entry and (time.time() - entry['ts'] < _RECOMMEND_CACHE_TTL):
        return entry['data']
    return None


def recommend_cache_set(key: str, data):
    """设置缓存值"""
    _param_recommend_cache[key] = {'ts': time.time(), 'data': data}


# 兼容原 main.py 中的下划线命名别名
_recommend_cache_key = recommend_cache_key
_recommend_cache_get = recommend_cache_get
_recommend_cache_set = recommend_cache_set
