# -*- coding: utf-8 -*-
"""
成型机台 26 项核心工艺参数状态与推荐对比独立模块 (Standalone Prototype)
====================================================================
本文件为独立原型实现，不依赖外部路由改造，包含：
1. 26 项核心成型工艺参数的标准元数据字典
2. 多源适配读取器（优先直连读取服务器共享目录历史 Parquet 文件，本地 CSV 兜底）
3. 机台基准状态三级时间回退检索机制 (Fallback Mechanism)
4. 结果值相加计算（ParameterValue + TechOffsetValue / TechOffsetHistoryValueTo）
5. 双列并排对比、本次修改项高亮标记、置顶排序、未修改项变动列完全留空
6. 命令行自测与表格化格式输出 (CLI Runner)
"""

import os
import sys
import glob
import re
import time
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np

# 确保在 Windows 控制台下输出 UTF-8，防止 GBK 编码异常
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# ==============================================================================
# 1. 26 项核心成型工艺参数元数据配置
# ==============================================================================

CORE_26_BUILDING_PARAMS = [
    {
        "id": 1190003,
        "name": "IL 安装摩擦",
        "global_name": "Lay-on friction IL",
        "unit": "%",
        "process_step": "内衬层 IL 贴合",
        "category": "摩擦力/贴合"
    },
    {
        "id": 1190005,
        "name": "安装高度_IL",
        "global_name": "Height",
        "unit": "mm",
        "process_step": "内衬层 IL 贴合",
        "category": "高度/位置"
    },
    {
        "id": 1190068,
        "name": "安装高度_PLY1",
        "global_name": "Height",
        "unit": "mm",
        "process_step": "帘布层 PLY1 贴合",
        "category": "高度/位置"
    },
    {
        "id": 1190075,
        "name": "顶部辊压力 PLY1",
        "global_name": "Toproll pressure lay on P1",
        "unit": "bar",
        "process_step": "帘布层 PLY1 压辊",
        "category": "压力"
    },
    {
        "id": 1190212,
        "name": "高度_SW",
        "global_name": "Height",
        "unit": "mm",
        "process_step": "胎侧 SW 贴合",
        "category": "高度/位置"
    },
    {
        "id": 1190259,
        "name": "左卷边罩位置_胎圈芯定位",
        "global_name": "Turn-up ring left position bead setting",
        "unit": "mm",
        "process_step": "胎圈反包定位 (左)",
        "category": "反包定位"
    },
    {
        "id": 1190260,
        "name": "右卷边罩位置_胎圈芯定位",
        "global_name": "Turn-up ring right position bead setting",
        "unit": "mm",
        "process_step": "胎圈反包定位 (右)",
        "category": "反包定位"
    },
    {
        "id": 1190261,
        "name": "卷边终端压力冲击",
        "global_name": "Turn-up end pressure shock",
        "unit": "bar",
        "process_step": "反包成型压力",
        "category": "压力"
    },
    {
        "id": 1190269,
        "name": "胶囊充气后的卷边罩等待时间",
        "global_name": "Turn-up rings delay after bladder inflation",
        "unit": "s",
        "process_step": "卷边充气时序",
        "category": "时间/节拍"
    },
    {
        "id": 1190293,
        "name": "左侧胶囊高压时间",
        "global_name": "Bladder left time high pressure",
        "unit": "s",
        "process_step": "胶囊高压反包 (左)",
        "category": "时间/节拍"
    },
    {
        "id": 1190294,
        "name": "右侧胶囊高压时间",
        "global_name": "Bladder right time high pressure",
        "unit": "s",
        "process_step": "胶囊高压反包 (右)",
        "category": "时间/节拍"
    },
    {
        "id": 1190316,
        "name": "安装位置_IL",
        "global_name": "Lay-on position",
        "unit": "mm",
        "process_step": "内衬层 IL 轴向定位",
        "category": "高度/位置"
    },
    {
        "id": 1191574,
        "name": "安装位置_SSR",
        "global_name": "Lay On Position SSR",
        "unit": "mm",
        "process_step": "缺气保用加强胶 SSR",
        "category": "高度/位置"
    },
    {
        "id": 1190318,
        "name": "安装位置_PLY1",
        "global_name": "Lay-on position",
        "unit": "mm",
        "process_step": "帘布层 PLY1 轴向定位",
        "category": "高度/位置"
    },
    {
        "id": 1190319,
        "name": "安装位置_PLY2",
        "global_name": "Lay-on position",
        "unit": "mm",
        "process_step": "帘布层 PLY2 轴向定位",
        "category": "高度/位置"
    },
    {
        "id": 1190338,
        "name": "IL 安装速度",
        "global_name": "Lay-on speed IL",
        "unit": "m/min",
        "process_step": "内衬层贴合速度",
        "category": "速度"
    },
    {
        "id": 1190349,
        "name": "PLY 1 安装速度",
        "global_name": "Lay-on speed PLY 1",
        "unit": "m/min",
        "process_step": "帘布层贴合速度",
        "category": "速度"
    },
    {
        "id": 1190066,
        "name": "PLY 1 安装摩擦",
        "global_name": "Lay-on friction PLY 1",
        "unit": "%",
        "process_step": "帘布层贴合摩擦力",
        "category": "摩擦力/贴合"
    },
    {
        "id": 1191577,
        "name": "SSR 安装摩擦",
        "global_name": "Lay-on friction SSR",
        "unit": "%",
        "process_step": "加强胶贴合摩擦力",
        "category": "摩擦力/贴合"
    },
    {
        "id": 1190073,
        "name": "径向位置 PLY 1",
        "global_name": "Position radial PLY 1",
        "unit": "mm",
        "process_step": "径向贴合深度",
        "category": "高度/位置"
    },
    {
        "id": 1190251,
        "name": "左侧波纹管式支撑件胎圈芯放置位置",
        "global_name": "Bladder unit left bead-setting position",
        "unit": "mm",
        "process_step": "胎圈撑件定位 (左)",
        "category": "反包定位"
    },
    {
        "id": 1190272,
        "name": "胎圈芯放置时间",
        "global_name": "Bead setting time",
        "unit": "s",
        "process_step": "胎圈装载时序",
        "category": "时间/节拍"
    },
    {
        "id": 1190323,
        "name": "安装位置_SW",
        "global_name": "Lay-on position",
        "unit": "mm",
        "process_step": "胎侧 SW 轴向定位",
        "category": "高度/位置"
    },
    {
        "id": 1190392,
        "name": "SW 安装速度",
        "global_name": "Lay-on speed SW",
        "unit": "m/min",
        "process_step": "胎侧贴合速度",
        "category": "速度"
    },
    {
        "id": 1190395,
        "name": "左侧波纹管式支撑件安装位置",
        "global_name": "Bladder unit left lay-on position",
        "unit": "mm",
        "process_step": "支撑件轴向位置 (左)",
        "category": "反包定位"
    },
    {
        "id": 1190396,
        "name": "右侧波纹管式支撑件安装位置",
        "global_name": "Bladder unit right lay-on position",
        "unit": "mm",
        "process_step": "支撑件轴向位置 (右)",
        "category": "反包定位"
    }
]

# 快速映射索引：按 ParameterID、LocalName 映射元数据
PARAM_BY_ID = {p["id"]: p for p in CORE_26_BUILDING_PARAMS}
PARAM_BY_NAME = {p["name"]: p for p in CORE_26_BUILDING_PARAMS}
ALL_PARAM_IDS = set(PARAM_BY_ID.keys())


# ==============================================================================
# 2. 稳健清洗与浮点转换工具
# ==============================================================================

def safe_float(val: Any, default: float = 0.0) -> float:
    """稳健地将任意输入（包含带引号的字符串、空格、None、NaN）转换为 float"""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if np.isnan(val):
            return default
        return float(val)
    # 处理字符串格式，如 "'0.0000'", " 12.5 ", "null"
    s = str(val).strip().strip("'").strip('"')
    if not s or s.lower() in ("nan", "none", "null", ""):
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def format_num(val: float, precision: int = 2) -> str:
    """美观格式化数值，自动消除末尾无效 0，如 12.50 -> 12.5, 10.00 -> 10"""
    rounded = round(val, precision)
    # 如果接近整数，直接输出整数字符串
    if abs(rounded - int(rounded)) < 1e-6:
        return str(int(rounded))
    s = f"{rounded:.{precision}f}".rstrip('0').rstrip('.')
    return s


# ==============================================================================
# 3. 多源数据加载器 (直读服务器 Parquet，本地 CSV 兜底)
# ==============================================================================

SERVER_DIR = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\CGRS_full_history_data"
LOCAL_CSV = os.path.join(os.path.dirname(__file__), "data", "Status-CGRS.csv")


class StatusParamDataLoader:
    """
    机台状态数据加载器
    1. 优先直连读取服务器网络共享目录 \\10.246.97.159... 下的日切片 parquet
    2. 网络不通或未找到时，回退至本地 backend/data/Status-CGRS.csv
    3. 维护内存缓存以提升检索性能
    """

    def __init__(self):
        self.server_dir = SERVER_DIR
        self.local_csv = LOCAL_CSV
        self.is_server_available: Optional[bool] = None
        self._date_file_map: Dict[str, str] = {}
        self._cache_by_date: Dict[str, pd.DataFrame] = {}
        self._local_df: Optional[pd.DataFrame] = None
        self._init_available_dates()

    def _init_available_dates(self):
        """扫描服务器上所有可用的 parquet 文件并建立 日期 -> 文件路径 映射"""
        self._date_file_map.clear()
        try:
            if os.path.exists(self.server_dir):
                self.is_server_available = True
                pattern = os.path.join(self.server_dir, "recipe_full_params_*.parquet")
                files = glob.glob(pattern)
                for f in files:
                    # 从文件名提取日期 YYYY-MM-DD
                    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
                    if m:
                        self._date_file_map[m.group(1)] = f
                print(f"[DataLoader] 成功连通服务器目录，找到 {len(self._date_file_map)} 个日期切片文件。")
            else:
                self.is_server_available = False
                print(f"[DataLoader] 未能连通服务器目录 {self.server_dir}，将使用本地 CSV 作为兜底。")
        except Exception as e:
            self.is_server_available = False
            print(f"[DataLoader] 访问服务器目录异常 ({e})，将使用本地 CSV 作为兜底。")

    def get_available_dates(self) -> List[str]:
        """返回所有可用的切片日期（按先后升序排列）"""
        if self.is_server_available and self._date_file_map:
            return sorted(list(self._date_file_map.keys()))
        # 否则读取本地 CSV 中包含的所有日期
        df_local = self._get_local_df()
        if df_local is not None and not df_local.empty:
            date_col = 'RecipeLastModifiedDate' if 'RecipeLastModifiedDate' in df_local.columns else 'RecipeCreatedDate'
            dates = df_local[date_col].dropna().astype(str).str[:10].unique().tolist()
            return sorted([d for d in dates if re.match(r"^\d{4}-\d{2}-\d{2}$", d)])
        return []

    def _get_local_df(self) -> Optional[pd.DataFrame]:
        """按需加载本地 CSV 底表（带缓存）"""
        if self._local_df is not None:
            return self._local_df
        if not os.path.exists(self.local_csv):
            print(f"[DataLoader] 本地 CSV 文件不存在: {self.local_csv}")
            return None
        try:
            # 本地 CSV 包含中文，尝试多种常用编码
            for enc in ['gb18030', 'gbk', 'utf-8-sig']:
                try:
                    df = pd.read_csv(self.local_csv, encoding=enc, low_memory=False)
                    # 规范化列名
                    df['ParameterID'] = pd.to_numeric(df['ParameterID'], errors='coerce')
                    self._local_df = df
                    print(f"[DataLoader] 成功加载本地 CSV 底表 ({enc}): {len(df)} 行。")
                    return self._local_df
                except Exception:
                    continue
        except Exception as e:
            print(f"[DataLoader] 加载本地 CSV 失败: {e}")
        return None

    def load_date_slice(self, date_str: str) -> Optional[pd.DataFrame]:
        """读取指定日期的切片数据"""
        if date_str in self._cache_by_date:
            return self._cache_by_date[date_str]

        # 1. 优先从服务器对应日期的 Parquet 加载
        if self.is_server_available and date_str in self._date_file_map:
            fpath = self._date_file_map[date_str]
            try:
                # 仅载入关键列以极致提升性能
                cols = [
                    'Workcenter', 'ParameterID', 'ParameterLocalName',
                    'ParameterGlobalName', 'ParameterValue', 'TechOffsetValue',
                    'RecipeLastModifiedDate'
                ]
                df = pd.read_parquet(fpath)
                # 确保关键列存在
                avail_cols = [c for c in cols if c in df.columns]
                df = df[avail_cols].copy()
                df['ParameterID'] = pd.to_numeric(df['ParameterID'], errors='coerce')
                self._cache_by_date[date_str] = df
                return df
            except Exception as e:
                print(f"[DataLoader] 读取服务器 Parquet {fpath} 出错: {e}，尝试本地兜底")

        # 2. 本地 CSV 兜底提取该日期的切片
        df_local = self._get_local_df()
        if df_local is not None:
            date_col = 'RecipeLastModifiedDate' if 'RecipeLastModifiedDate' in df_local.columns else 'RecipeCreatedDate'
            mask = df_local[date_col].astype(str).str.startswith(date_str)
            sub_df = df_local[mask].copy()
            if not sub_df.empty:
                self._cache_by_date[date_str] = sub_df
                return sub_df

        return None


# 全局共享加载器单例
data_loader = StatusParamDataLoader()


# ==============================================================================
# 4. 机台状态三级时间回退检索核心
# ==============================================================================

def get_machine_candidates(wc: str) -> List[str]:
    """生成成型机台别名候选池，确保 TB2xx 与 CGRS 底表中的 TB1xx 完美互通"""
    clean = wc.strip().upper()
    cands = [clean]
    if clean.startswith("TB2"):
        cands.append(f"TB1{clean[3:]}")
        cands.append(f"TB{clean[3:]}")
    elif clean.startswith("TB1"):
        cands.append(f"TB2{clean[3:]}")
        cands.append(f"TB{clean[3:]}")
    return list(dict.fromkeys(cands))


def get_machine_status_snapshot(
    machine: str,
    target_date: Optional[str] = None
) -> Tuple[Dict[int, Dict[str, Any]], str, str]:
    """
    严格限制时间天花板的时间回溯检索机制 (严禁跨入未来日期)：
    1. 优先匹配 target_date 当天该机台的参数记录；
    2. 若当天无记录，回溯在 target_date 之前距离最近的一天；
    3. 若无早于 target_date 的历史切片，直接返回未查询到，绝不读取未来数据。
    """
    cands = get_machine_candidates(machine)
    avail_dates = data_loader.get_available_dates()

    if not avail_dates:
        return {}, "", "no_data"

    if not target_date:
        target_date = avail_dates[-1]

    # 1. Level 1: 尝试匹配 target_date 当天
    if target_date in avail_dates:
        df_day = data_loader.load_date_slice(target_date)
        if df_day is not None:
            mach_sub = df_day[df_day['Workcenter'].astype(str).str.upper().isin(cands)]
            if not mach_sub.empty:
                snapshot = _extract_26_params_from_df(mach_sub)
                if snapshot:
                    return snapshot, target_date, "exact_match"

    # 2. Level 2: 回溯 target_date 之前最近的日期 (严格 d <= target_date)
    earlier_dates = [d for d in avail_dates if d <= target_date]
    earlier_dates.sort(reverse=True)
    for d in earlier_dates:
        df_day = data_loader.load_date_slice(d)
        if df_day is not None:
            mach_sub = df_day[df_day['Workcenter'].astype(str).str.upper().isin(cands)]
            if not mach_sub.empty:
                snapshot = _extract_26_params_from_df(mach_sub)
                if snapshot:
                    return snapshot, d, "fallback_earlier"

    return {}, target_date, "no_valid_history_snapshot"


def _extract_26_params_from_df(df_mach: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
    """从单个机台的数据框中抽取并锁定 26 项核心成型参数"""
    res = {}
    # 只过滤 26 项目标参数 ID
    sub = df_mach[df_mach['ParameterID'].isin(ALL_PARAM_IDS)].copy()

    # 如果有重复行（比如同一天有多次修改），以最后一次修改或最后一行生效记录为准
    sub = sub.drop_duplicates(subset=['ParameterID'], keep='last')

    for _, r in sub.iterrows():
        pid = int(r['ParameterID'])
        base_val = safe_float(r.get('ParameterValue'), 0.0)
        offset_val = safe_float(r.get('TechOffsetValue'), 0.0)
        # 结果值 = ParameterValue + TechOffsetValue
        current_res_val = base_val + offset_val

        res[pid] = {
            "parameter_id": pid,
            "parameter_value": base_val,
            "tech_offset_value": offset_val,
            "current_value": current_res_val,
            "local_name": str(r.get('ParameterLocalName', '')).strip(),
            "global_name": str(r.get('ParameterGlobalName', '')).strip()
        }
    return res


# ==============================================================================
# 5. 核心计算与结果对比生成器
# ==============================================================================

def calculate_status_recommendation_comparison(
    machine: str,
    target_date: Optional[str] = None,
    recommendation_events: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    计算并生成机台 26 项核心成型参数的完整对比报表：
    
    【核心计算口径】:
    1. 目前状态值 = ParameterValue + TechOffsetValue
    2. 推荐状态值:
       - 若该参数在 recommendation_events 中被修改:
         修改前值 = ParameterValue + TechOffsetHistoryValueFrom
         推荐状态值 = ParameterValue + TechOffsetHistoryValueTo
         修改变化 = 推荐状态值 - 目前状态值 (带正负号)
         高亮标记 = True
       - 若未被修改:
         推荐状态值 = 目前状态值 (保持现状)
         修改变化 = None / "" (完全留空，不填！)
         高亮标记 = False
    3. 排序规则:
       修改项高亮并置顶排序在前，其余参数保持标准工步顺序排列。
    """
    # 1. 获取机台基准状态快照
    status_snapshot, actual_baseline_date, fallback_level = get_machine_status_snapshot(
        machine=machine,
        target_date=target_date
    )

    # 2. 建立推荐事件中被修改参数的快速检索字典 (支持按 ID 或参数名匹配)
    rec_modifications_by_id: Dict[int, Dict[str, Any]] = {}
    rec_modifications_by_name: Dict[str, Dict[str, Any]] = {}

    if recommendation_events:
        for ev in recommendation_events:
            # 支持传入扁平参数列表或事件结构
            params_list = ev.get('params', [ev]) if isinstance(ev, dict) else [ev]
            for p in params_list:
                p_id = p.get('ParameterID') or p.get('parameter_id')
                p_name = str(p.get('ParameterLocalName') or p.get('param_name') or '').strip()
                p_gname = str(p.get('ParameterName') or p.get('param_global_name') or '').strip()

                mod_info = {
                    "raw": p,
                    "val_from": safe_float(p.get('TechOffsetHistoryValueFrom', p.get('setting_from'))),
                    "val_to": safe_float(p.get('TechOffsetHistoryValueTo', p.get('setting_to'))),
                    "base_val": p.get('ParameterValue')  # 若有
                }

                if p_id and safe_float(p_id, 0) > 0:
                    rec_modifications_by_id[int(safe_float(p_id))] = mod_info
                if p_name:
                    rec_modifications_by_name[p_name] = mod_info
                if p_gname:
                    rec_modifications_by_name[p_gname] = mod_info

    # 3. 对 26 项核心参数逐项计算结果值
    rows = []
    total_changed_count = 0

    for idx, meta in enumerate(CORE_26_BUILDING_PARAMS, 1):
        pid = meta["id"]
        pname = meta["name"]
        unit = meta["unit"]
        global_name = meta["global_name"]

        # 获取该参数在底表中的基准状态
        curr_snap = status_snapshot.get(pid, {})
        base_val = curr_snap.get("parameter_value", 0.0)
        curr_offset = curr_snap.get("tech_offset_value", 0.0)
        curr_res_val = curr_snap.get("current_value", base_val + curr_offset)

        # 检查是否被推荐事件修改
        mod_item = None
        if pid in rec_modifications_by_id:
            mod_item = rec_modifications_by_id[pid]
        elif pname in rec_modifications_by_name:
            mod_item = rec_modifications_by_name[pname]
        elif global_name in rec_modifications_by_name and global_name != "Height" and global_name != "Lay-on position":
            # 避免 Height / Lay-on position 这种通用重名英文名误匹配，特异性英文名才允许
            mod_item = rec_modifications_by_name[global_name]

        if mod_item is not None:
            # ──────── 情形 A: 本次推荐涉及该参数 ────────
            if mod_item.get("setting_to") is not None and str(mod_item.get("setting_to")).strip() != "":
                rec_res_val = safe_float(mod_item["setting_to"], curr_res_val)
            elif mod_item.get("base_val") is not None and mod_item.get("val_to") is not None:
                rec_res_val = safe_float(mod_item["base_val"], 0.0) + safe_float(mod_item["val_to"], 0.0)
            elif mod_item.get("val_to") is not None:
                rec_res_val = base_val + safe_float(mod_item["val_to"], 0.0)
            elif mod_item.get("base_val") is not None:
                rec_res_val = safe_float(mod_item["base_val"], curr_res_val)
            else:
                rec_res_val = curr_res_val

            # 修改变化 = 推荐状态值 - 目前状态值
            diff = rec_res_val - curr_res_val
            if abs(diff) > 1e-5:
                # 只有真正存在数值差别的，才作为参数推荐改动提示并高亮置顶！
                total_changed_count += 1
                is_changed = True
                change_str = f"+{format_num(diff)}" if diff > 0 else f"{format_num(diff)}"
                change_val = diff
            else:
                # 变化量为 0 的直接不作为参数推荐改动提示：完全留空，不置顶不高亮
                is_changed = False
                rec_res_val = curr_res_val
                change_str = ""
                change_val = None
        else:
            # ──────── 情形 B: 本次推荐未修改该参数 ────────
            is_changed = False
            # 推荐状态值 = 目前状态值 (保持原设定不变)
            rec_res_val = curr_res_val
            # 变化列完全留空！不填任何内容！
            change_str = ""
            change_val = None

        rows.append({
            "original_order": idx,
            "parameter_id": pid,
            "param_name": pname,
            "param_global_name": global_name,
            "unit": unit,
            "process_step": meta["process_step"],
            "category": meta["category"],
            "current_value": round(curr_res_val, 3),
            "current_value_formatted": format_num(curr_res_val),
            "recommended_value": round(rec_res_val, 3),
            "recommended_value_formatted": format_num(rec_res_val),
            "change": change_str,
            "change_value": change_val,
            "is_changed": is_changed,
            "has_base_record": (pid in status_snapshot)
        })

    # 4. 排序规则：修改项置顶，其余项保持原有工步顺序
    rows.sort(key=lambda x: (0 if x["is_changed"] else 1, x["original_order"]))

    return {
        "machine": machine,
        "query_target_date": target_date,
        "baseline_status_date": actual_baseline_date,
        "fallback_level": fallback_level,
        "total_params": len(rows),
        "changed_params_count": total_changed_count,
        "status_comparison": rows
    }


# ==============================================================================
# 6. 终端美观表格输出与自测运行入口 (CLI Runner)
# ==============================================================================

def print_comparison_table(result: Dict[str, Any]):
    """将对比结果以整齐对齐的控制台表格打印出来"""
    mach = result["machine"]
    req_date = result["query_target_date"]
    base_date = result["baseline_status_date"]
    fb_level = result["fallback_level"]
    cnt_changed = result["changed_params_count"]
    rows = result["status_comparison"]

    print("=" * 115)
    print(f" ⚙️ 机台成型核心 26 项工艺参数对比表 | 机台: {mach} | 基准日期: {base_date} (回溯状态: {fb_level})")
    print(f" 📊 观察日: {req_date} | 26项参数涵盖数: {len(rows)} | 本次推荐修改项数: {cnt_changed}")
    print("=" * 115)

    header = f"{'序号':<4} | {'核心参数名称 (Local)':<26} | {'单位':<5} | {'目前状态值':>10} | {'推荐状态值':>10} | {'修改变化':^10} | {'状态标识':^8} | {'监控工步'}"
    print(header)
    print("-" * 115)

    for i, r in enumerate(rows, 1):
        name_str = r['param_name']
        unit_str = r['unit']
        curr_str = r['current_value_formatted']
        rec_str = r['recommended_value_formatted']
        chg_str = r['change']  # 未修改项留空
        flag_str = "⭐ 改动" if r['is_changed'] else ""
        step_str = r['process_step']

        # 高亮提示（控制台展示）
        line = f"{i:<4} | {name_str:<24} | {unit_str:<5} | {curr_str:>10} | {rec_str:>10} | {chg_str:^10} | {flag_str:^8} | {step_str}"
        print(line)

    print("=" * 115)
    print(" 💡 注：未修改的参数，【推荐状态值】维持原设定，【修改变化】列保持完全留空。\n")


if __name__ == "__main__":
    print("\n🚀 [Standalone Test] 正在启动成型机台 26 项参数推荐与状态对比独立自检...\n")
    t0 = time.time()

    # 1. 探查可用日期列表
    dates = data_loader.get_available_dates()
    print(f"📌 系统当前可用切片日期: {dates}\n")

    # 2. 模拟真实业务场景测试 1: TB122 在 2026-09-04，有 3 项参数推荐修改
    # 模拟从优质调参事件中获取的 3 项修改建议:
    #   - 顶部辊压力 PLY1 (1190075): 原偏置 0.0 -> 修改后 0.5 (增加 0.5 bar)
    #   - 左卷边罩位置_胎圈芯定位 (1190259): 原偏置 -2.0 -> 修改后 -3.5 (减少 1.5 mm)
    #   - IL 安装速度 (1190338): 原偏置 0.0 -> 修改后 5.0 (提速 5.0 m/min)
    mock_events_tb122 = [
        {
            "ParameterID": 1190075,
            "ParameterLocalName": "顶部辊压力 PLY1",
            "TechOffsetHistoryValueFrom": 0.0,
            "TechOffsetHistoryValueTo": 0.5,
            "ParameterValue": 2.0
        },
        {
            "ParameterID": 1190259,
            "ParameterLocalName": "左卷边罩位置_胎圈芯定位",
            "TechOffsetHistoryValueFrom": -2.0,
            "TechOffsetHistoryValueTo": -3.5,
            "ParameterValue": 150.0
        },
        {
            "ParameterID": 1190338,
            "ParameterLocalName": "IL 安装速度",
            "TechOffsetHistoryValueFrom": 0.0,
            "TechOffsetHistoryValueTo": 5.0,
            "ParameterValue": 30.0
        }
    ]

    print("▶️ 执行测试 1: 机台 TB122 (观察日: 2026-09-04, 含有 3 项推荐修改)")
    res_tb122 = calculate_status_recommendation_comparison(
        machine="TB122",
        target_date="2026-09-04",
        recommendation_events=mock_events_tb122
    )
    print_comparison_table(res_tb122)

    # 3. 模拟业务场景测试 2: 机台当天无记录，测试三级时间回溯 (例如查询 2026-09-06，当天无记录，回溯最近日 2026-09-05 或 2026-09-04)
    print("▶️ 执行测试 2: 机台 TB122 (观察日: 2026-09-06，当天无切片，验证时间自动回溯)")
    res_fallback = calculate_status_recommendation_comparison(
        machine="TB122",
        target_date="2026-09-06",
        recommendation_events=None  # 无新修改事件，纯展示基准状态
    )
    print_comparison_table(res_fallback)

    # 4. 模拟业务场景测试 3: 另一台成型机 TB111
    print("▶️ 执行测试 3: 成型机 TB111 (观察日: 2026-09-04)")
    res_tb111 = calculate_status_recommendation_comparison(
        machine="TB111",
        target_date="2026-09-04",
        recommendation_events=None
    )
    print_comparison_table(res_tb111)

    print(f"✅ 自检完成，总耗时: {round(time.time() - t0, 3)} 秒\n")
