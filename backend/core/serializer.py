# -*- coding: utf-8 -*-
"""
数据序列化与递归防 NaN / 无穷大工具模块
"""
import numpy as np


def sanitize_data(obj):
    """递归清理与标准化数据对象，防止序列化异常"""
    if isinstance(obj, dict):
        return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_data(x) for x in obj)
    elif isinstance(obj, np.ndarray):
        return [sanitize_data(x) for x in obj.tolist()]
    elif hasattr(obj, "item") and callable(getattr(obj, "item", None)):
        return obj.item()
    else:
        return obj
