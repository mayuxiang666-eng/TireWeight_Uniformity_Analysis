# -*- coding: utf-8 -*-
"""
多工序机台核心工艺参数基准状态与推荐对比服务 (Status CGRS Service)
=====================================================================
承接 CGRS 推荐接口，在看板各机台「查看推荐参数」弹窗中提供：
1. CU 硫化 (14项)、TB2 成型二段 PU (30项)、TB1 成型一段 KM (26项) 核心工艺参数定义与自适应切换
2. 真实生产底表双源高可用检索：
   - 提取配方基准值：选定日全量表 -> 历史全量切片 -> 调参变动日志随路记录
   - 提取机台当前生效偏置：按选定日期历史回溯取最近一次生效偏置
3. 四列状态对比生成：
   - 第 1 列：【当前参数状态】 (ParameterValue + 机台当前生效偏置)
   - 第 2 列：【推荐修改前状态】 (修改项: ParameterValue + TechOffsetHistoryValueFrom; 未修改项: 保持当前参数状态)
   - 第 3 列：【推荐修改后状态】 (修改项: ParameterValue + TechOffsetHistoryValueTo; 未修改项: 保持当前参数状态)
   - 第 4 列：【修改变化】 (修改项: 差值带正负号; 未修改项: 完全留空不填)
4. 修改项高亮置顶，未修改项按原有工步顺序展示
"""

import os
import glob
import re
from typing import Dict, List, Any, Optional, Tuple, Set
import duckdb
import pandas as pd
import numpy as np


# ==============================================================================
# 1. 核心工艺参数元数据配置 (KM 26项, PU 30项, CU 14项)
# ==============================================================================

# 1.1 成型一段 KM (ProcessTypeID: 119 - 26项)
CORE_KM_BUILDING_PARAMS = [
    {"id": 1190003, "name": "IL 安装摩擦", "global_name": "Lay-on friction IL", "sys_name": "TB1_IL_Friction", "unit": "%", "process_step": "内衬层 IL 贴合", "category": "摩擦力/贴合"},
    {"id": 1190005, "name": "安装高度_IL", "global_name": "Height", "sys_name": "TB1_IL_HeightServicer", "unit": "mm", "process_step": "内衬层 IL 贴合", "category": "高度/位置"},
    {"id": 1190068, "name": "安装高度_PLY1", "global_name": "Height", "sys_name": "TB1_PL1_HeightServicer", "unit": "mm", "process_step": "帘布层 PLY1 贴合", "category": "高度/位置"},
    {"id": 1190075, "name": "顶部辊压力 PLY1", "global_name": "Toproll pressure lay on P1", "sys_name": "TB1_PL1_PressureTopRoll", "unit": "bar", "process_step": "帘布层 PLY1 压辊", "category": "压力"},
    {"id": 1190212, "name": "高度_SW", "global_name": "Height", "sys_name": "TB1_SW_HeightServicer", "unit": "mm", "process_step": "胎侧 SW 贴合", "category": "高度/位置"},
    {"id": 1190259, "name": "左卷边罩位置_胎圈芯定位", "global_name": "Turn-up ring left position bead setting", "sys_name": "TB1_BS_PositionSettingBeadLeft", "unit": "mm", "process_step": "胎圈反包定位 (左)", "category": "反包定位"},
    {"id": 1190260, "name": "右卷边罩位置_胎圈芯定位", "global_name": "Turn-up ring right position bead setting", "sys_name": "TB1_BS_PositionSettingBeadRight", "unit": "mm", "process_step": "胎圈反包定位 (右)", "category": "反包定位"},
    {"id": 1190261, "name": "卷边终端压力冲击", "global_name": "Turn-up end pressure shock", "sys_name": "TB1_BS_PressureHighRing", "unit": "bar", "process_step": "反包成型压力", "category": "压力"},
    {"id": 1190269, "name": "胶囊充气后的卷边罩等待时间", "global_name": "Turn-up rings delay after bladder inflation", "sys_name": "TB1_BS_TimeBeadFixationDelay", "unit": "s", "process_step": "卷边充气时序", "category": "时间/节拍"},
    {"id": 1190293, "name": "左侧胶囊高压时间", "global_name": "Bladder left time high pressure", "sys_name": "TB1_TUP_TimeShockHighPressureLeft", "unit": "s", "process_step": "胶囊高压反包 (左)", "category": "时间/节拍"},
    {"id": 1190294, "name": "右侧胶囊高压时间", "global_name": "Bladder right time high pressure", "sys_name": "TB1_TUP_TimeShockHighPressureRight", "unit": "s", "process_step": "胶囊高压反包 (右)", "category": "时间/节拍"},
    {"id": 1190316, "name": "安装位置_IL", "global_name": "Lay-on position", "sys_name": "TB1_IL_DistanceServicerToDrum", "unit": "mm", "process_step": "内衬层 IL 轴向定位", "category": "高度/位置"},
    {"id": 1191574, "name": "安装位置_SSR", "global_name": "Lay On Position SSR", "sys_name": "TB1_SSR_DistanceServicerToDrum", "unit": "mm", "process_step": "缺气保用加强胶 SSR", "category": "高度/位置"},
    {"id": 1190318, "name": "安装位置_PLY1", "global_name": "Lay-on position", "sys_name": "TB1_PL1_DistanceServicerToDrum", "unit": "mm", "process_step": "帘布层 PLY1 轴向定位", "category": "高度/位置"},
    {"id": 1190319, "name": "安装位置_PLY2", "global_name": "Lay-on position", "sys_name": "TB1_PL2_DistanceServicerToDrum", "unit": "mm", "process_step": "帘布层 PLY2 轴向定位", "category": "高度/位置"},
    {"id": 1190338, "name": "IL 安装速度", "global_name": "Lay-on speed IL", "sys_name": "TB1_IL_SpeedLayonDrum", "unit": "m/min", "process_step": "内衬层贴合速度", "category": "速度"},
    {"id": 1190349, "name": "PLY 1 安装速度", "global_name": "Lay-on speed PLY 1", "sys_name": "TB1_PL1_SpeedLayonDrum", "unit": "m/min", "process_step": "帘布层贴合速度", "category": "速度"},
    {"id": 1190066, "name": "PLY 1 安装摩擦", "global_name": "Lay-on friction PLY 1", "sys_name": "TB1_PL1_Friction", "unit": "%", "process_step": "帘布层贴合摩擦力", "category": "摩擦力/贴合"},
    {"id": 1191577, "name": "SSR 安装摩擦", "global_name": "Lay-on friction SSR", "sys_name": "TB1_SSR_Friction", "unit": "%", "process_step": "加强胶贴合摩擦力", "category": "摩擦力/贴合"},
    {"id": 1190073, "name": "径向位置 PLY 1", "global_name": "Position radial PLY 1", "sys_name": "TB1_PL1_PositionTopRollRadial", "unit": "mm", "process_step": "径向贴合深度", "category": "高度/位置"},
    {"id": 1190251, "name": "左侧波纹管式支撑件胎圈芯放置位置", "global_name": "Bladder unit left bead-setting position", "sys_name": "TB1_BS_PositionBladderLeft", "unit": "mm", "process_step": "胎圈撑件定位 (左)", "category": "反包定位"},
    {"id": 1190272, "name": "胎圈芯放置时间", "global_name": "Bead setting time", "sys_name": "TB1_BS_TimeResident", "unit": "s", "process_step": "胎圈装载时序", "category": "时间/节拍"},
    {"id": 1190323, "name": "安装位置_SW", "global_name": "Lay-on position", "sys_name": "TB1_SW_DistanceServicerToDrum", "unit": "mm", "process_step": "胎侧 SW 轴向定位", "category": "高度/位置"},
    {"id": 1190392, "name": "SW 安装速度", "global_name": "Lay-on speed SW", "sys_name": "TB1_SW_SpeedLayonDrum", "unit": "m/min", "process_step": "胎侧贴合速度", "category": "速度"},
    {"id": 1190395, "name": "左侧波纹管式支撑件安装位置", "global_name": "Bladder unit left lay-on position", "sys_name": "TB1_BS_PositionBladderLeftLayon", "unit": "mm", "process_step": "支撑件轴向位置 (左)", "category": "反包定位"},
    {"id": 1190396, "name": "右侧波纹管式支撑件安装位置", "global_name": "Bladder unit right lay-on position", "sys_name": "TB1_BS_PositionBladderRightLayon", "unit": "mm", "process_step": "支撑件轴向位置 (右)", "category": "反包定位"}
]

# 1.2 成型二段 PU (ProcessTypeID: 125 - 30项)
CORE_PU_BUILDING_PARAMS = [
    {"id": 1250094, "name": "胎面安装位置", "global_name": "Tread lay-on position", "sys_name": "TB2_TR_DistanceServicerToDrum", "unit": "mm", "process_step": "胎面贴合", "category": "高度/位置"},
    {"id": 1250128, "name": "带束层传输位置", "global_name": "Belt package transfer position", "sys_name": "TB2_BPT_PositionDrumTransfer", "unit": "mm", "process_step": "带束层传输", "category": "高度/位置"},
    {"id": 1250495, "name": "胎面检查位置", "global_name": "GTTS Stop for tire check (0=deactivated)", "sys_name": "TB2_GTTS_StopCheck", "unit": "mm", "process_step": "胎面检查", "category": "高度/位置"},
    {"id": 1252086, "name": "BL安装速度", "global_name": "BL lay-on speed", "sys_name": "TB2_BL_SpeedLayonDrum", "unit": "m/min", "process_step": "带束层BL贴合", "category": "速度"},
    {"id": 1252096, "name": "BR安装速度", "global_name": "BR lay-on speed", "sys_name": "TB2_BR_SpeedLayonDrum", "unit": "m/min", "process_step": "带束层BR贴合", "category": "速度"},
    {"id": 1250068, "name": "TR安装速度", "global_name": "Tread lay-on speed", "sys_name": "TB2_TR_SpeedLayonDrum", "unit": "m/min", "process_step": "胎面TR贴合", "category": "速度"},
    {"id": 1250143, "name": "BTR", "global_name": "BTR diameter", "sys_name": "TB2_BT_DiameterDrum", "unit": "mm", "process_step": "贴合鼓", "category": "直径/几何"},
    {"id": 1250421, "name": "铁液罐距离", "global_name": "LC4 - Distance to center (Spec card)", "sys_name": "TB2_LC_DistanceCenter4", "unit": "mm", "process_step": "铁液罐定位", "category": "高度/位置"},
    {"id": 1250280, "name": "BD1胎面切割位置", "global_name": "BD 1 Tread Cutting Position", "sys_name": "TB2_BD1_PositionCut", "unit": "mm", "process_step": "胎面切割", "category": "高度/位置"},
    {"id": 1250281, "name": "BD2胎面切割位置", "global_name": "BD 2 Tread Cutting Position", "sys_name": "TB2_BD2_PositionCut", "unit": "mm", "process_step": "胎面切割", "category": "高度/位置"},
    {"id": 1250284, "name": "结合分段安装压力", "global_name": "Splice segments lay-on pressure", "sys_name": "TB2_SP_PressureSegmentLayon", "unit": "bar", "process_step": "接合分段", "category": "压力"},
    {"id": 1250285, "name": "结合分段接合压力", "global_name": "Splice segments splice pressure", "sys_name": "TB2_SP_PressureSegmentSplice", "unit": "bar", "process_step": "接合分段", "category": "压力"},
    {"id": 1250283, "name": "滚压辊压力", "global_name": "Pressure roller pressure", "sys_name": "TB2_PR_PressureRoller", "unit": "bar", "process_step": "滚压成型", "category": "压力"},
    {"id": 1250499, "name": "后定心辊压力", "global_name": "Pressure centering roll rear", "sys_name": "TB2_CR_PressureRollRear", "unit": "bar", "process_step": "定心辊", "category": "压力"},
    {"id": 1250498, "name": "中间定心辊压力", "global_name": "Pressure centering roll middle", "sys_name": "TB2_CR_PressureRollMiddle", "unit": "bar", "process_step": "定心辊", "category": "压力"},
    {"id": 1250497, "name": "前定心辊压力", "global_name": "Pressure centering roll front", "sys_name": "TB2_CR_PressureRollFront", "unit": "bar", "process_step": "定心辊", "category": "压力"},
    {"id": 1250091, "name": "带滚压辊速度", "global_name": "Belt stitcher speed", "sys_name": "TB2_BS_SpeedStitcher", "unit": "m/min", "process_step": "滚压成型", "category": "速度"},
    {"id": 1252361, "name": "BL到BD的间距", "global_name": "BL distance to BD", "sys_name": "TB2_BL_DistanceBD", "unit": "mm", "process_step": "带束层定位", "category": "高度/位置"},
    {"id": 1252377, "name": "BR到BD的间距", "global_name": "BR distance to BD", "sys_name": "TB2_BR_DistanceBD", "unit": "mm", "process_step": "带束层定位", "category": "高度/位置"},
    {"id": 1250148, "name": "SH放置胎体位置", "global_name": "SH carcass setting position (Spec card)", "sys_name": "TB2_SH_PositionCarcassSetting", "unit": "mm", "process_step": "成型机头SH", "category": "高度/位置"},
    {"id": 1250149, "name": "SH拉伸胎体位置", "global_name": "SH carcass spreading position (Spec card)", "sys_name": "TB2_SH_PositionCarcassSpreading", "unit": "mm", "process_step": "成型机头SH", "category": "高度/位置"},
    {"id": 1250146, "name": "SH预弯曲成型位置", "global_name": "SH pre-shaping position (Spec card)", "sys_name": "TB2_SH_PositionPreshaping", "unit": "mm", "process_step": "预弯曲成型", "category": "高度/位置"},
    {"id": 1250150, "name": "SH滚压位置", "global_name": "SH stitching position (Spec card)", "sys_name": "TB2_SH_PositionStitching", "unit": "mm", "process_step": "滚压成型", "category": "高度/位置"},
    {"id": 1250147, "name": "取出轮胎的SH位置", "global_name": "SH remove tyre position (0=OFF)", "sys_name": "TB2_SH_PositionRemoveTyre", "unit": "mm", "process_step": "取胎定位", "category": "高度/位置"},
    {"id": 1250153, "name": "SH预弯曲成型压力", "global_name": "SH pressure pre-shaping", "sys_name": "TB2_SH_PressurePreshaping", "unit": "bar", "process_step": "预弯曲成型", "category": "压力"},
    {"id": 1250154, "name": "压制胎纹的 SH 压力", "global_name": "SH pressure shaping", "sys_name": "TB2_SH_PressureShaping", "unit": "bar", "process_step": "胎纹压制", "category": "压力"},
    {"id": 1250156, "name": "SH滚压压力", "global_name": "SH pressure stitching", "sys_name": "TB2_SH_PressureStitching", "unit": "bar", "process_step": "滚压成型", "category": "压力"},
    {"id": 1250296, "name": "CTR直径", "global_name": "CTR diameter", "sys_name": "TB2_CTR_Diameter", "unit": "mm", "process_step": "定型环直径", "category": "直径/几何"},
    {"id": 1250297, "name": "胎体装料机直径", "global_name": "Carcass loader diameter", "sys_name": "TB2_CL_Diameter", "unit": "mm", "process_step": "装料机定位", "category": "直径/几何"},
    {"id": 1250299, "name": "胎体装载装置宽度偏移", "global_name": "Offset carcass loader width (0=OFF)", "sys_name": "TB2_CL_OffsetWidth", "unit": "mm", "process_step": "装载宽度偏移", "category": "高度/位置"}
]

# 1.3 硫化工序 CU (ProcessTypeID: 123 - 14项)
CORE_CU_CURING_PARAMS = [
    {"id": 1230307, "name": "合模力", "global_name": "Squeeze Pressure", "sys_name": "CU_Squeeze_Pressure", "unit": "kN", "process_step": "合模加压", "category": "压力"},
    {"id": 1230030, "name": "机械手装胎高度", "global_name": "Loader Shaping Position", "sys_name": "CU_Loader_Shaping_Position", "unit": "mm", "process_step": "机械手装胎", "category": "高度/位置"},
    {"id": 1230273, "name": "二次定型-新胶囊", "global_name": "Shapepressure 2 new bladder", "sys_name": "CU_Shapepressure_2_New", "unit": "bar", "process_step": "新胶囊定型", "category": "压力"},
    {"id": 1230275, "name": "一次定型-新胶囊", "global_name": "Shapepressure 1 new bladder", "sys_name": "CU_Shapepressure_1_New", "unit": "bar", "process_step": "新胶囊定型", "category": "压力"},
    {"id": 1230294, "name": "一次定型", "global_name": "Shaping Step 1", "sys_name": "CU_Shaping_Step_1", "unit": "bar", "process_step": "胶囊一次定型", "category": "压力"},
    {"id": 1230296, "name": "二次定型", "global_name": "Shaping Step 2", "sys_name": "CU_Shaping_Step_2", "unit": "bar", "process_step": "胶囊二次定型", "category": "压力"},
    {"id": 1230265, "name": "中心机构定型位置（生胎高度）", "global_name": "Center Post Shaping Pos. (Green Tire Height)", "sys_name": "CU_Center_Post_Shaping_Pos", "unit": "mm", "process_step": "中心机构定位", "category": "高度/位置"},
    {"id": 1230287, "name": "定型阀门开启度（新胶囊）", "global_name": "Shaping Max. Open (New Bladder)", "sys_name": "CU_Shaping_Max_Open_New", "unit": "%", "process_step": "阀门开度", "category": "开度/流量"},
    {"id": 1230288, "name": "定型阀门开启度", "global_name": "Shaping Max. Open", "sys_name": "CU_Shaping_Max_Open", "unit": "%", "process_step": "阀门开度", "category": "开度/流量"},
    {"id": 1231163, "name": "合模暂停时间", "global_name": "Time Shaping Stop", "sys_name": "CU_Time_Shaping_Stop", "unit": "s", "process_step": "合模时序控制", "category": "时间/节拍"},
    {"id": 1231164, "name": "开模暂停时间", "global_name": "Time Opening Stop", "sys_name": "CU_Time_Opening_Stop", "unit": "s", "process_step": "开模时序控制", "category": "时间/节拍"},
    {"id": 1230385, "name": "开模暂停位置（机器）", "global_name": "Position Opening Stop (press)", "sys_name": "CU_Position_Opening_Stop", "unit": "mm", "process_step": "开模定位", "category": "高度/位置"},
    {"id": 1230483, "name": "下环下降延迟（在脱模时）", "global_name": "Delay Lower Ring down (at Demolding)", "sys_name": "CU_Delay_Lower_Ring_Down", "unit": "s", "process_step": "脱模时序", "category": "时间/节拍"},
    {"id": 1230208, "name": "开模暂停开关", "global_name": "Open stop yes/no", "sys_name": "CU_Open_Stop_Enabled", "unit": "-", "process_step": "开模时序控制", "category": "开关/状态"}
]


def get_core_params_for_machine(
    machine: str,
    workcenter_type: Optional[str] = None,
    recommendation_events: Optional[List[Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], str, str]:
    """根据机台名称、工段类型及推荐参数事件，智能自适应路由核心参数清单"""
    m_clean = str(machine).strip().upper()
    wc_type = str(workcenter_type or "").strip().lower()

    # 1. 硫化工序 CU
    if m_clean.startswith("CU") or m_clean.startswith("CT") or wc_type in ("curing", "ct", "cu"):
        return CORE_CU_CURING_PARAMS, "123", "CU 硫化工序"

    # 2. 检查推荐事件中是否明确为一段 (TB1/KM/119) 或二段 (TB2/PU/125)
    if recommendation_events:
        for ev in recommendation_events:
            p_list = ev.get('params', [ev]) if isinstance(ev, dict) else [ev]
            for p in p_list:
                p_name = str(p.get('param_name') or p.get('ParameterName') or p.get('param_global_name') or '').upper()
                p_id = str(p.get('ParameterID') or p.get('parameter_id') or '')
                p_proc = str(p.get('ProcessTypeID') or p.get('process_type_id') or '')
                if p_name.startswith('TB1') or p_proc == '119' or (p_id.startswith('119') and len(p_id) == 7):
                    return CORE_KM_BUILDING_PARAMS, "119", "KM 成型一段工序"
                if p_name.startswith('TB2') or p_proc == '125' or (p_id.startswith('125') and len(p_id) == 7):
                    return CORE_PU_BUILDING_PARAMS, "125", "PU 成型二段工序"

    # 3. 默认按机台名称前缀路由
    if m_clean.startswith("TB2") or wc_type in ("pu", "tb2", "stage2"):
        return CORE_PU_BUILDING_PARAMS, "125", "PU 成型二段工序"

    return CORE_KM_BUILDING_PARAMS, "119", "KM 成型一段工序"


# ==============================================================================
# 2. 稳健清洗与格式化工具
# ==============================================================================

def safe_float(val: Any, default: float = 0.0) -> float:
    """稳健将任意字符串/数值转换为 float"""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if np.isnan(val):
            return default
        return float(val)
    s = str(val).strip().strip("'").strip('"')
    if not s or s.lower() in ("nan", "none", "null", ""):
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def format_num(val: Optional[float], precision: int = 2) -> str:
    """消除无效末尾 0 的美观数值格式化"""
    if val is None:
        return "-"
    rounded = round(val, precision)
    if abs(rounded - int(rounded)) < 1e-6:
        return str(int(rounded))
    return f"{rounded:.{precision}f}".rstrip('0').rstrip('.')


def _norm_str(s: Any) -> str:
    """消除空格、下划线、短横线并统一小写"""
    if not s:
        return ""
    return re.sub(r'[\s_\-]+', '', str(s).strip().lower())


# ==============================================================================
# 3. 真实生产底表数据检索服务 (严格零临时表)
# ==============================================================================

SERVER_FULL_DIR = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\CGRS_full_history_data"
SERVER_CHANGES_DIR = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data"


def get_machine_candidates(wc: str) -> List[str]:
    """生成机台别名候选池，确保 TB2xx 与底表中的 TB1xx / TBxx 完美互通"""
    clean = wc.strip().upper()
    cands = [clean]
    if clean.startswith("TB2"):
        cands.append(f"TB1{clean[3:]}")
        cands.append(f"TB{clean[3:]}")
    elif clean.startswith("TB1"):
        cands.append(f"TB2{clean[3:]}")
        cands.append(f"TB{clean[3:]}")
    elif clean.startswith("CU") and not clean.startswith("CUG"):
        cands.append(f"CUG{clean[2:]}")
    elif clean.startswith("CUG"):
        cands.append(f"CU{clean[3:]}")
    return list(dict.fromkeys(cands))


def extract_spec_keywords(article10: Optional[str]) -> List[str]:
    """提取规格核心识别关键词（7位代码、纯数字主核），用于高召回匹配 MaterialMasterID"""
    if not article10:
        return []
    clean = str(article10).strip()
    keys = [clean]
    if len(clean) >= 7:
        art7 = clean[:7]
        keys.append(art7)
        if art7.startswith("0"):
            keys.append(art7[1:])  # 去掉前导0 (例如 0312781 -> 312781)
    return list(dict.fromkeys(keys))


def get_parameter_base_values(
    article10: Optional[str],
    process_type_id: str,
    target_date: Optional[str] = None,
    machine: Optional[str] = None
) -> Dict[int, float]:
    """
    根据选定日期 target_date 获取配方基准值 ParameterValue:
    - 优先匹配 target_date 当天的全量快照 (recipe_full_params_{target_date}.parquet)
    - 若 target_date 当天无切片 (例如早于 2026-09-03 或未落盘)，自动回退匹配现有可用全量底表，提取标准 ParameterValue
    - CU 硫化 (123): 硫化参数直接按机台匹配；若机台无匹配再按规格兜底
    - 成型工序 (KM 119 / PU 125): 按规格 MaterialMasterID 识别关键词过滤匹配
    """
    base_values: Dict[int, float] = {}
    if not os.path.exists(SERVER_FULL_DIR):
        return base_values

    target_day = str(target_date).strip()[:10] if target_date else ""
    target_f = os.path.join(SERVER_FULL_DIR, f"recipe_full_params_{target_day}.parquet") if target_day else ""

    candidate_files = []
    if target_f and os.path.exists(target_f):
        candidate_files.append(target_f)

    # 扫描目录下所有的全量切片并按日期降序排序 (优先最近快照)
    all_full_files = sorted(glob.glob(os.path.join(SERVER_FULL_DIR, "recipe_full_params_*.parquet")), reverse=True)
    for f in all_full_files:
        if f not in candidate_files:
            candidate_files.append(f)

    if not candidate_files:
        return base_values

    proc_str = str(process_type_id).strip()
    is_cu = (proc_str == "123") or (machine and (str(machine).upper().startswith("CU") or str(machine).upper().startswith("CT")))
    spec_keys = extract_spec_keywords(article10)

    con = duckdb.connect()

    for f_path in candidate_files:
        try:
            if is_cu and machine:
                cands = get_machine_candidates(machine)
                cands_sql = "', '".join(cands)
                spec_filter_part = ""
                if article10 and article10.strip():
                    p7 = article10.strip()[:7]
                    spec_filter_part = f"AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = '{p7}' OR CAST(MaterialMasterID AS VARCHAR) LIKE '%{p7}%')"

                q = f"""
                SELECT TRY_CAST(ParameterID AS BIGINT) as pid, ANY_VALUE(ParameterValue) as ParameterValue
                FROM read_parquet('{f_path}', union_by_name=true)
                WHERE Workcenter IN ('{cands_sql}')
                  AND TRY_CAST(ProcessTypeID AS VARCHAR) = '123'
                  {spec_filter_part}
                GROUP BY TRY_CAST(ParameterID AS BIGINT)
                """
                df = con.execute(q).df()
                if not df.empty:
                    for _, r in df.iterrows():
                        if pd.notna(r['pid']) and pd.notna(r['ParameterValue']):
                            base_values[int(r['pid'])] = safe_float(r['ParameterValue'])
                if base_values:
                    return base_values

            # 成型工序 (或 CU 兜底): 按规格代码精准识别匹配
            if spec_keys:
                spec_conditions = []
                for k in spec_keys:
                    spec_conditions.append(f"MaterialMasterID LIKE '%{k}%'")
                    spec_conditions.append(f"MaterialMasterID = '{k}'")
                spec_filter_sql = " OR ".join(spec_conditions)

                q = f"""
                SELECT TRY_CAST(ParameterID AS BIGINT) as pid, ANY_VALUE(ParameterValue) as ParameterValue
                FROM read_parquet('{f_path}', union_by_name=true)
                WHERE ({spec_filter_sql})
                  AND TRY_CAST(ProcessTypeID AS VARCHAR) = '{process_type_id}'
                GROUP BY TRY_CAST(ParameterID AS BIGINT)
                """
                df = con.execute(q).df()
                if not df.empty:
                    for _, r in df.iterrows():
                        if pd.notna(r['pid']) and pd.notna(r['ParameterValue']):
                            base_values[int(r['pid'])] = safe_float(r['ParameterValue'])
                if base_values:
                    return base_values
        except Exception:
            continue

    return base_values


def get_machine_current_offsets(
    machine: str,
    target_date: Optional[str] = None,
    article10: Optional[str] = None,
    process_type_id: str = "119"
) -> Tuple[Dict[int, float], Dict[int, str], Dict[int, float]]:
    """
    回溯提取机台当前生效偏置、生效日期及变动日志随路记录的配方基准值:
    - 100% 严格从变动日志 (recipe_offset_changes_*.parquet) 中检索
    - 过滤条件: Workcenter 属于机台候选池，且时间 <= target_date 23:59:59
    - 成型工序如果传入规格 article10，优先按 ProdSpecific2 匹配同规格调参
    - 取时间倒序最新一条的 TechOffsetHistoryValueTo 及 TechOffsetHistoryLocalDate
    - 【重要业务准则】：若历史上无修改记录，该参数不放入 offsets（表示无记录，前端显示 '-'，坚决不默认 0.0）
    - 彻底废除向全量表读取 TechOffsetValue 兜底
    返回: (offsets_dict, offset_dates_dict, change_pvs_dict)
    """
    offsets: Dict[int, float] = {}
    offset_dates: Dict[int, str] = {}
    change_pvs: Dict[int, float] = {}
    cands = get_machine_candidates(machine)
    cands_sql = "', '".join(cands)
    ref_date_sql = f"{target_date} 23:59:59" if target_date else "2099-12-31 23:59:59"

    if not os.path.exists(SERVER_CHANGES_DIR):
        return offsets, offset_dates, change_pvs

    con = duckdb.connect()
    pattern = f"{SERVER_CHANGES_DIR}\\recipe_offset_changes_*.parquet"

    proc_str = str(process_type_id).strip()
    is_cu = (proc_str == "123") or (str(machine).upper().startswith("CU") or str(machine).upper().startswith("CT"))

    try:
        # 1. 如果是成型工序且有规格，优先匹配同机台同规格的调参记录
        if not is_cu and article10:
            spec_keys = extract_spec_keywords(article10)
            if spec_keys:
                spec_conds = " OR ".join([f"ProdSpecific2 LIKE '%{k}%'" for k in spec_keys])
                q_spec = f"""
                SELECT 
                    TRY_CAST(ParameterID AS BIGINT) as pid,
                    TechOffsetHistoryValueTo as offset_val,
                    ParameterValue,
                    COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as change_time
                FROM read_parquet('{pattern}', union_by_name=true)
                WHERE Workcenter IN ('{cands_sql}')
                  AND ({spec_conds})
                  AND COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) <= '{ref_date_sql}'
                  AND TechOffsetHistoryValueTo IS NOT NULL
                ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
                """
                df_spec = con.execute(q_spec).df()
                if not df_spec.empty:
                    dedup = df_spec.drop_duplicates(subset=['pid'], keep='first')
                    for _, r in dedup.iterrows():
                        if pd.notna(r['pid']) and pd.notna(r['offset_val']):
                            p_id = int(r['pid'])
                            offsets[p_id] = safe_float(r['offset_val'])
                            raw_date = str(r['change_time']) if pd.notna(r['change_time']) else ''
                            offset_dates[p_id] = raw_date[:16] if len(raw_date) >= 16 else (raw_date[:10] if raw_date else str(target_date or ''))
                            if pd.notna(r['ParameterValue']):
                                change_pvs[p_id] = safe_float(r['ParameterValue'])

        # 1.2 如果是 CU 硫化工序且有规格，严格按 MaterialMasterID 后7位与规格前7位匹配同机台同规格调参记录
        elif is_cu and article10 and article10.strip():
            p7 = article10.strip()[:7]
            q_spec = f"""
            SELECT 
                TRY_CAST(ParameterID AS BIGINT) as pid,
                TechOffsetHistoryValueTo as offset_val,
                ParameterValue,
                COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as change_time
            FROM read_parquet('{pattern}', union_by_name=true)
            WHERE Workcenter IN ('{cands_sql}')
              AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = '{p7}' OR CAST(MaterialMasterID AS VARCHAR) LIKE '%{p7}%')
              AND COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) <= '{ref_date_sql}'
              AND TechOffsetHistoryValueTo IS NOT NULL
            ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
            """
            df_spec = con.execute(q_spec).df()
            if not df_spec.empty:
                dedup = df_spec.drop_duplicates(subset=['pid'], keep='first')
                for _, r in dedup.iterrows():
                    if pd.notna(r['pid']) and pd.notna(r['offset_val']):
                        p_id = int(r['pid'])
                        offsets[p_id] = safe_float(r['offset_val'])
                        raw_date = str(r['change_time']) if pd.notna(r['change_time']) else ''
                        offset_dates[p_id] = raw_date[:16] if len(raw_date) >= 16 else (raw_date[:10] if raw_date else str(target_date or ''))
                        if pd.notna(r['ParameterValue']):
                            change_pvs[p_id] = safe_float(r['ParameterValue'])

        # 2. 如果成型工序未在规格中匹配到的参数，或机台未传入规格时的全机台兜底（CU工序若传入规格则严禁跨规格继承）
        if not (is_cu and article10 and article10.strip()):
            q_all = f"""
            SELECT 
                TRY_CAST(ParameterID AS BIGINT) as pid,
                TechOffsetHistoryValueTo as offset_val,
                ParameterValue,
                COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as change_time
            FROM read_parquet('{pattern}', union_by_name=true)
            WHERE Workcenter IN ('{cands_sql}')
              AND COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) <= '{ref_date_sql}'
              AND TechOffsetHistoryValueTo IS NOT NULL
            ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
            """
            df_all = con.execute(q_all).df()
            if not df_all.empty:
                dedup_all = df_all.drop_duplicates(subset=['pid'], keep='first')
                for _, r in dedup_all.iterrows():
                    if pd.notna(r['pid']) and pd.notna(r['offset_val']):
                        p_id = int(r['pid'])
                        if p_id not in offsets:
                            offsets[p_id] = safe_float(r['offset_val'])
                            raw_date = str(r['change_time']) if pd.notna(r['change_time']) else ''
                            offset_dates[p_id] = raw_date[:16] if len(raw_date) >= 16 else (raw_date[:10] if raw_date else str(target_date or ''))
                            if pd.notna(r['ParameterValue']):
                                change_pvs[p_id] = safe_float(r['ParameterValue'])
    except Exception:
        pass

    return offsets, offset_dates, change_pvs


def get_machine_offset_at_cutoff(
    machine: str,
    cutoff_time_str: str,
    article10: Optional[str] = None,
    process_type_id: str = "119"
) -> Tuple[Dict[int, float], Dict[int, str]]:
    """
    检索指定机台在 cutoff_time_str 之前的最后一次生效偏置（用于非修改项状态提取）
    若该机台在该时刻前从未修改过该参数，则该参数不在返回字典中（即无记录，显示为 '-'）
    """
    offsets: Dict[int, float] = {}
    offset_dates: Dict[int, str] = {}
    if not cutoff_time_str or not os.path.exists(SERVER_CHANGES_DIR):
        return offsets, offset_dates

    cands = get_machine_candidates(machine)
    cands_sql = "', '".join(cands)
    con = duckdb.connect()
    pattern = f"{SERVER_CHANGES_DIR}\\recipe_offset_changes_*.parquet"

    proc_str = str(process_type_id).strip()
    is_cu = (proc_str == "123") or (str(machine).upper().startswith("CU") or str(machine).upper().startswith("CT"))

    try:
        if not is_cu and article10:
            spec_keys = extract_spec_keywords(article10)
            if spec_keys:
                spec_conds = " OR ".join([f"ProdSpecific2 LIKE '%{k}%'" for k in spec_keys])
                q_spec = f"""
                SELECT 
                    TRY_CAST(ParameterID AS BIGINT) as pid,
                    TechOffsetHistoryValueTo as offset_val,
                    COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as change_time
                FROM read_parquet('{pattern}', union_by_name=true)
                WHERE Workcenter IN ('{cands_sql}')
                  AND ({spec_conds})
                  AND COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) <= '{cutoff_time_str}'
                  AND TechOffsetHistoryValueTo IS NOT NULL
                ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
                """
                df_spec = con.execute(q_spec).df()
                if not df_spec.empty:
                    dedup = df_spec.drop_duplicates(subset=['pid'], keep='first')
                    for _, r in dedup.iterrows():
                        if pd.notna(r['pid']) and pd.notna(r['offset_val']):
                            p_id = int(r['pid'])
                            offsets[p_id] = safe_float(r['offset_val'])
                            raw_date = str(r['change_time']) if pd.notna(r['change_time']) else ''
                            offset_dates[p_id] = raw_date[:16] if len(raw_date) >= 16 else (raw_date[:10] if raw_date else "")

        elif is_cu and article10 and article10.strip():
            p7 = article10.strip()[:7]
            q_spec = f"""
            SELECT 
                TRY_CAST(ParameterID AS BIGINT) as pid,
                TechOffsetHistoryValueTo as offset_val,
                COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as change_time
            FROM read_parquet('{pattern}', union_by_name=true)
            WHERE Workcenter IN ('{cands_sql}')
              AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = '{p7}' OR CAST(MaterialMasterID AS VARCHAR) LIKE '%{p7}%')
              AND COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) <= '{cutoff_time_str}'
              AND TechOffsetHistoryValueTo IS NOT NULL
            ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
            """
            df_spec = con.execute(q_spec).df()
            if not df_spec.empty:
                dedup = df_spec.drop_duplicates(subset=['pid'], keep='first')
                for _, r in dedup.iterrows():
                    if pd.notna(r['pid']) and pd.notna(r['offset_val']):
                        p_id = int(r['pid'])
                        offsets[p_id] = safe_float(r['offset_val'])
                        raw_date = str(r['change_time']) if pd.notna(r['change_time']) else ''
                        offset_dates[p_id] = raw_date[:16] if len(raw_date) >= 16 else (raw_date[:10] if raw_date else "")

        if not (is_cu and article10 and article10.strip()):
            q_all = f"""
            SELECT 
                TRY_CAST(ParameterID AS BIGINT) as pid,
                TechOffsetHistoryValueTo as offset_val,
                COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as change_time
            FROM read_parquet('{pattern}', union_by_name=true)
            WHERE Workcenter IN ('{cands_sql}')
              AND COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) <= '{cutoff_time_str}'
              AND TechOffsetHistoryValueTo IS NOT NULL
            ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
            """
            df_all = con.execute(q_all).df()
            if not df_all.empty:
                dedup_all = df_all.drop_duplicates(subset=['pid'], keep='first')
                for _, r in dedup_all.iterrows():
                    if pd.notna(r['pid']) and pd.notna(r['offset_val']):
                        p_id = int(r['pid'])
                        if p_id not in offsets:
                            offsets[p_id] = safe_float(r['offset_val'])
                            raw_date = str(r['change_time']) if pd.notna(r['change_time']) else ''
                            offset_dates[p_id] = raw_date[:16] if len(raw_date) >= 16 else (raw_date[:10] if raw_date else "")
    except Exception:
        pass

    return offsets, offset_dates


# ==============================================================================
# 4. 推荐改前、改后与当前状态四列状态组装服务 (按确认技术口径重构)
# ==============================================================================

def calculate_status_recommendation_comparison(
    machine: str,
    article10: Optional[str] = None,
    workcenter_type: Optional[str] = None,
    target_date: Optional[str] = None,
    recommendation_events: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    计算并生成机台核心工艺参数四列状态对比报表:
    - 第 1 列：【当前参数状态】 (ParameterValue + 修改记录表最近一次生效的 TechOffsetHistoryValueTo；若无修改记录则显示为 -)
    - 第 2 列：【推荐修改前状态】 (修改项: ParameterValue + TechOffsetHistoryValueFrom; 未修改项: 检索推荐机台当时偏置，无则显示 -)
    - 第 3 列：【推荐修改后状态】 (修改项: ParameterValue + TechOffsetHistoryValueTo; 未修改项: 检索推荐机台当时偏置，无则显示 -)
    - 第 4 列：【修改变化】 (推荐修改后状态 - 当前参数状态，未修改项或含 - 项留空不填)
    """
    core_params, proc_id, proc_name = get_core_params_for_machine(
        machine=machine,
        workcenter_type=workcenter_type,
        recommendation_events=recommendation_events
    )

    # 1. 获取规格配方基准值字典 {pid: base_val} (全量表抽取，支持回退至可用切片)
    base_values = get_parameter_base_values(
        article10=article10,
        process_type_id=proc_id,
        target_date=target_date,
        machine=machine
    )

    # 2. 获取当前机台历史生效偏置字典 {pid: offset}、生效日期字典 {pid: date_str}，及变动日志随路基准值 {pid: pv}
    # 严格从变动日志获取最新生效值，无记录时不填充默认值 (不放入 current_offsets)
    current_offsets, current_offset_dates, change_pvs = get_machine_current_offsets(
        machine=machine,
        target_date=target_date,
        article10=article10,
        process_type_id=proc_id
    )

    # 3. 解析推荐事件中的具体改动参数及推荐事件发生日期
    rec_mod_by_id: Dict[int, Dict[str, Any]] = {}
    rec_mod_by_key: Dict[str, Dict[str, Any]] = {}
    global_rec_event_time = ""
    rec_machine = machine

    if recommendation_events:
        for ev in recommendation_events:
            ev_time = (
                ev.get('event_time') or ev.get('best_event_time') or
                ev.get('event_date') or ev.get('TechOffsetLocalDate') or
                ev.get('date_time_str') or ev.get('timestamp')
            )
            if ev_time and not global_rec_event_time:
                global_rec_event_time = str(ev_time).strip()

            ev_mach = ev.get('workcenter') or ev.get('Workcenter') or ev.get('machine')
            if ev_mach:
                rec_machine = str(ev_mach).strip()

            params_list = ev.get('params', [ev]) if isinstance(ev, dict) else [ev]
            for p in params_list:
                p_id = p.get('ParameterID') or p.get('parameter_id')

                val_from = safe_float(p.get('TechOffsetHistoryValueFrom', p.get('val_from', 0.0)))
                val_to = safe_float(p.get('TechOffsetHistoryValueTo', p.get('val_to', 0.0)))

                p_time = (
                    p.get('event_time') or p.get('TechOffsetLocalDate') or
                    p.get('date_time_str') or p.get('timestamp') or global_rec_event_time
                )
                p_time_str = str(p_time).strip() if p_time else ""

                mod_info = {
                    "raw": p,
                    "val_from": val_from,
                    "val_to": val_to,
                    "setting_from": p.get('setting_from'),
                    "setting_to": p.get('setting_to'),
                    "event_time": p_time_str[:16] if len(p_time_str) >= 16 else (p_time_str[:10] if p_time_str else "")
                }

                if p_id and safe_float(p_id, 0) > 0:
                    rec_mod_by_id[int(safe_float(p_id))] = mod_info

                for field in ['ParameterLocalName', 'param_local_name', 'ParameterName', 'param_name', 'ParameterGlobalName', 'param_global_name']:
                    val = p.get(field)
                    if val:
                        s_val = str(val).strip()
                        rec_mod_by_key[s_val] = mod_info
                        rec_mod_by_key[_norm_str(s_val)] = mod_info

    # 4. 针对推荐机台，检索其在推荐事件发生时刻当时的生效偏置 (用于未修改项的状态提取)
    rec_cutoff_time = global_rec_event_time if global_rec_event_time else (f"{target_date} 23:59:59" if target_date else "")
    rec_machine_offsets, rec_machine_offset_dates = get_machine_offset_at_cutoff(
        machine=rec_machine,
        cutoff_time_str=rec_cutoff_time,
        article10=article10,
        process_type_id=proc_id
    )

    rows = []
    total_changed_count = 0

    for idx, meta in enumerate(core_params, 1):
        pid = meta["id"]
        pname = meta["name"]
        sys_name = meta.get("sys_name", "")
        global_name = meta["global_name"]
        unit = meta["unit"]

        # ─── 基准值与当前参数状态 ───
        base_val = base_values.get(pid)
        if base_val is None and pid in change_pvs:
            base_val = change_pvs[pid]

        # 【核心口径 1】：若该机台该参数在变动日志中无修改记录，坚决不假设偏置为 0，直接显示为 '-'
        if pid in current_offsets:
            curr_offset = current_offsets[pid]
            curr_offset_date = current_offset_dates.get(pid)
            if base_val is not None:
                curr_val = base_val + curr_offset
            else:
                curr_val = curr_offset
            current_status_date = curr_offset_date
            is_offset_inherited = bool(
                curr_offset_date and target_date and str(curr_offset_date)[:10] != str(target_date)[:10]
            )
            inherited_date = curr_offset_date if is_offset_inherited else None
        else:
            curr_val = None
            curr_offset_date = None
            current_status_date = None
            is_offset_inherited = False
            inherited_date = None

        # ─── 匹配推荐事件 ───
        mod_item = None
        if pid in rec_mod_by_id:
            mod_item = rec_mod_by_id[pid]
        elif pname in rec_mod_by_key:
            mod_item = rec_mod_by_key[pname]
        elif _norm_str(pname) in rec_mod_by_key:
            mod_item = rec_mod_by_key[_norm_str(pname)]
        elif sys_name and sys_name in rec_mod_by_key:
            mod_item = rec_mod_by_key[sys_name]
        elif sys_name and _norm_str(sys_name) in rec_mod_by_key:
            mod_item = rec_mod_by_key[_norm_str(sys_name)]
        elif global_name in rec_mod_by_key and global_name not in ("Height", "Lay-on position"):
            mod_item = rec_mod_by_key[global_name]
        elif _norm_str(global_name) in rec_mod_by_key and global_name not in ("Height", "Lay-on position"):
            mod_item = rec_mod_by_key[_norm_str(global_name)]

        if mod_item is not None:
            # ──────── 情形 A: 本次推荐事件涉及该参数（修改项） ────────
            is_changed = True
            total_changed_count += 1

            val_from = mod_item["val_from"]
            val_to = mod_item["val_to"]
            rec_date = mod_item.get("event_time") or global_rec_event_time[:16] or target_date or ""

            if base_val is not None:
                pre_rec_val = base_val + val_from
                post_rec_val = base_val + val_to
            elif pid in change_pvs and change_pvs[pid] is not None:
                pre_rec_val = change_pvs[pid] + val_from
                post_rec_val = change_pvs[pid] + val_to
            elif mod_item.get("setting_to") is not None and mod_item.get("setting_from") is not None:
                pre_rec_val = safe_float(mod_item["setting_from"])
                post_rec_val = safe_float(mod_item["setting_to"])
            else:
                pre_rec_val = val_from
                post_rec_val = val_to

            # 修改变化：严格等于【推荐修改后状态】 - 【当前参数状态】
            if post_rec_val is not None and curr_val is not None:
                diff = post_rec_val - curr_val
                if abs(diff) >= 0.0001:
                    change_str = f"+{format_num(diff)}" if diff > 0 else f"{format_num(diff)}"
                    change_val = diff
                else:
                    change_str = "0"
                    change_val = 0.0
            else:
                diff = None
                change_str = ""
                change_val = None
        else:
            # ──────── 情形 B: 本次推荐未涉及该参数（未修改项） ────────
            is_changed = False
            rec_date = global_rec_event_time[:16] if global_rec_event_time else ""

            # 【核心口径 2】：非修改项检索推荐机台在推荐时刻前最近一次生效的偏置值；若无记录同样显示为 '-'
            if pid in rec_machine_offsets:
                rec_off = rec_machine_offsets[pid]
                if base_val is not None:
                    ev_val = base_val + rec_off
                else:
                    ev_val = rec_off
                pre_rec_val = ev_val
                post_rec_val = ev_val
            else:
                pre_rec_val = None
                post_rec_val = None

            # 计算当前状态与推荐设定之间的差值 (修改变化量 = 推荐修改后 - 当前状态)
            if post_rec_val is not None and curr_val is not None:
                diff = post_rec_val - curr_val
                if abs(diff) >= 0.0001:
                    change_str = f"+{format_num(diff)}" if diff > 0 else f"{format_num(diff)}"
                    change_val = diff
                else:
                    change_str = ""  # 与推荐完全一致，留空显示 -
                    change_val = 0.0
            else:
                diff = None
                change_str = ""
                change_val = None

        cur_fmt = format_num(curr_val) if curr_val is not None else "-"
        pre_fmt = format_num(pre_rec_val) if pre_rec_val is not None else "-"
        rec_fmt = format_num(post_rec_val) if post_rec_val is not None else "-"

        rows.append({
            "original_order": idx,
            "parameter_id": pid,
            "param_name": pname,
            "param_global_name": global_name,
            "unit": unit,
            "process_step": meta["process_step"],
            "category": meta["category"],
            # 1. 当前参数状态及其最后修改生效时间
            "current_value": round(curr_val, 3) if curr_val is not None else None,
            "current_value_formatted": cur_fmt,
            "current_status_display": cur_fmt,
            "current_status_date": current_status_date,
            "current_offset_date": curr_offset_date,
            "is_offset_inherited": is_offset_inherited,
            "inherited_date": inherited_date,
            # 2. 推荐修改前状态
            "pre_recommended_value": round(pre_rec_val, 3) if pre_rec_val is not None else None,
            "pre_recommended_value_formatted": pre_fmt,
            "recommend_before_display": pre_fmt,
            # 3. 推荐修改后状态及其调参选取日期
            "recommended_value": round(post_rec_val, 3) if post_rec_val is not None else None,
            "recommended_value_formatted": rec_fmt,
            "recommend_after_display": rec_fmt,
            "recommend_event_date": rec_date,
            "has_event_snapshot": (pre_rec_val is not None or is_changed),
            # 4. 修改变化
            "change": change_str,
            "change_value": change_val,
            "change_delta_display": change_str,
            "change_delta_value": change_val,
            "is_changed": is_changed,
            "has_base_record": (base_val is not None)
        })

    # 修改项高亮置顶，其余项按工艺工步顺序展示
    rows.sort(key=lambda x: (0 if x["is_changed"] else 1, x["original_order"]))

    # 检查是否所有推荐调整项的变化量均为 0 (全 0 状态判定)
    changed_rows = [r for r in rows if r["is_changed"]]
    all_zero_diff = False
    if changed_rows:
        all_zero_diff = all(abs(r.get("change_value") or 0.0) < 0.0001 for r in changed_rows)
        if all_zero_diff:
            for r in changed_rows:
                r["change"] = "已到达最佳参数"
                r["change_delta_display"] = "已到达最佳参数"

    return {
        "machine": machine,
        "recommend_machine": rec_machine,
        "article10": article10,
        "process_type": proc_name,
        "process_type_id": proc_id,
        "query_target_date": target_date,
        "current_base_date": target_date,
        "recommend_event_date": global_rec_event_time[:16] if global_rec_event_time else (target_date or ""),
        "has_current_snapshot": (len(base_values) > 0),
        "has_event_snapshot": any(r["has_event_snapshot"] for r in rows),
        "total_params": len(rows),
        "changed_params_count": total_changed_count,
        "has_status_snapshot": any(r["has_base_record"] for r in rows),
        "is_optimal_no_diff": all_zero_diff,
        "status_comparison": rows
    }
