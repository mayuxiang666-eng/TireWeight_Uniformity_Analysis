# -*- coding: utf-8 -*-
"""
交互式 Wiki、技术交接与 AI 问答服务路由 (Wiki & AI Assistant Router)
提供思维导图目录检索、文档读写持久化，以及内置领域大模型 AI 问答 API
"""
import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

# 动态定位项目路径
_ROUTER_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTER_DIR)
_ROOT_DIR = os.path.dirname(_BACKEND_DIR)  # d:\Ava\untitled1\untitled1_v2
_WORKSPACE_DIR = os.path.dirname(_ROOT_DIR)  # d:\Ava\untitled1

# 独立同级 Wiki 目录：优先加载 d:\Ava\untitled1\wiki
STANDALONE_WIKI_DIR = os.path.join(_WORKSPACE_DIR, "wiki")
if os.path.exists(STANDALONE_WIKI_DIR):
    WIKI_DIR = STANDALONE_WIKI_DIR
else:
    WIKI_DIR = os.path.join(_ROOT_DIR, "docs", "wiki")

WIKI_HTML_PATH = os.path.join(WIKI_DIR, "wiki.html")
if not os.path.exists(WIKI_HTML_PATH):
    WIKI_HTML_PATH = os.path.join(_ROOT_DIR, "docs", "wiki.html")

CATALOG_PATH = os.path.join(WIKI_DIR, "catalog.json")
AI_CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "ai_config.json")

os.makedirs(WIKI_DIR, exist_ok=True)
os.makedirs(os.path.join(_BACKEND_DIR, "config"), exist_ok=True)


def _safe_doc_path(doc_id: str) -> str:
    """清理并校验 doc_id，防止路径穿越风险"""
    clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '', doc_id)
    if not clean_id:
        raise HTTPException(status_code=400, detail="无效的文档标识符 (Invalid doc_id)")
    return os.path.join(WIKI_DIR, f"{clean_id}.md")


def _get_ai_config() -> Dict[str, Any]:
    """读取 AI 模型调用配置"""
    if os.path.exists(AI_CONFIG_PATH):
        try:
            with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "provider": "builtin",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini"
    }


def _save_ai_config(cfg: Dict[str, Any]) -> None:
    """保存 AI 模型调用配置"""
    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ==============================================================================
# Wiki 基础目录与文档 API
# ==============================================================================

@router.get("/wiki/catalog")
def get_wiki_catalog():
    """获取知识图谱与目录大纲元数据"""
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                return JSONResponse(content=json.load(f))
        except Exception as e:
            return JSONResponse(status_code=500, content={"status": "error", "message": f"读取目录失败: {str(e)}"})
    return JSONResponse(content={"status": "empty", "modules": []})


@router.get("/wiki/doc/{doc_id}")
def get_wiki_doc(doc_id: str):
    """读取指定模块的 Markdown 内容"""
    target_file = _safe_doc_path(doc_id)
    if not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        stat = os.stat(target_file)
        return {
            "status": "success",
            "doc_id": doc_id,
            "content": content,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文档失败: {str(e)}")


@router.post("/wiki/doc/{doc_id}")
def save_wiki_doc(doc_id: str, payload: dict = Body(...)):
    """保存并持久化回写 Markdown 文档到本地磁盘"""
    target_file = _safe_doc_path(doc_id)
    content = payload.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="缺少文档内容 (content is required)")
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "status": "success",
            "message": f"文档 {doc_id}.md 已成功持久化保存至本地磁盘",
            "doc_id": doc_id,
            "saved_at": now_str
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文档失败: {str(e)}")


@router.get("/wiki", response_class=HTMLResponse)
def serve_wiki_page():
    """直接在浏览器访问 /wiki 呈现交互式知识图谱、交接文档与 AI 助手"""
    if os.path.exists(WIKI_HTML_PATH):
        with open(WIKI_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>Wiki 页面正在生成中，请稍候刷新...</h2>", status_code=200)


# ==============================================================================
# AI 问答助手 API 与双模智能问答引擎 (Built-in RAG + External LLM)
# ==============================================================================

@router.get("/wiki/ai-config")
def get_ai_config_endpoint():
    """获取当前 AI 助手配置 (安全脱敏)"""
    cfg = _get_ai_config()
    api_key = cfg.get("api_key", "")
    masked_key = ""
    if api_key:
        if len(api_key) > 8:
            masked_key = api_key[:4] + "..." + api_key[-4:]
        else:
            masked_key = "********"
    return {
        "status": "success",
        "provider": cfg.get("provider", "builtin"),
        "base_url": cfg.get("base_url", "https://api.openai.com/v1"),
        "model": cfg.get("model", "gpt-4o-mini"),
        "has_key": bool(api_key),
        "masked_key": masked_key
    }


@router.post("/wiki/ai-config")
def set_ai_config_endpoint(payload: dict = Body(...)):
    """保存 AI 助手连接配置"""
    cfg = _get_ai_config()
    if "provider" in payload:
        cfg["provider"] = payload["provider"]
    if "base_url" in payload:
        cfg["base_url"] = payload["base_url"].strip().rstrip("/")
    if "model" in payload:
        cfg["model"] = payload["model"].strip()
    if "api_key" in payload and payload["api_key"] is not None:
        new_key = payload["api_key"].strip()
        if new_key and not new_key.startswith("..."):
            cfg["api_key"] = new_key
        elif new_key == "":
            cfg["api_key"] = ""
            cfg["provider"] = "builtin"

    _save_ai_config(cfg)
    return {
        "status": "success",
        "message": "AI 助手配置已持久化更新",
        "provider": cfg.get("provider"),
        "model": cfg.get("model")
    }


def _call_openai_compatible_api(base_url: str, api_key: str, model: str, system_prompt: str, user_message: str, history: List[dict]) -> str:
    """通过原生 urllib 调用 OpenAI / DeepSeek / Ollama / vLLM 兼容接口"""
    endpoint = f"{base_url}/chat/completions"
    
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history[-6:]:
            if "role" in item and "content" in item:
                messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_message})

    req_body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.3
    }).encode("utf-8")

    req = urllib.request.Request(endpoint, data=req_body, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return choices[0]["message"].get("content", "")
        return "未能从模型响应中获取有效文本"


def _call_gemini_api(api_key: str, model: str, system_prompt: str, user_message: str, history: List[dict]) -> str:
    """调用 Google Gemini 官方 API"""
    gemini_model = model if model.startswith("gemini") else "gemini-1.5-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"

    contents = []
    # 注入系统知识
    contents.append({"role": "user", "parts": [{"text": f"系统交接文档背景：\n{system_prompt}"}]})
    contents.append({"role": "model", "parts": [{"text": "已明确该系统的全流程技术文档与指标规则，请提问。"}]})

    if history:
        for item in history[-4:]:
            role = "user" if item.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": item.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    req_body = json.dumps({"contents": contents}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=req_body, method="POST")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return "Gemini 未返回有效文本"


def _builtin_knowledge_qa(user_message: str, current_doc_id: Optional[str] = None) -> str:
    """
    内置工业级知识图谱问答引擎 (离线即用，无需外部 API Key)
    覆盖 17项指标、DuckDB内存保护、CGRS因果拆分、平方根平滑、SOP排错与架构红线
    """
    q = user_message.lower().strip()

    # 1. 询问 平方根平滑 / 开满机台 / 负贡献 / 背黑锅
    if any(k in q for k in ["平方根", "平滑", "背黑锅", "开满", "impact_score", "volume", "sqrt"]):
        return (
            "### 产量平方根平滑算法 (Square-Root Volume Smoothing)\n\n"
            "**业务动因与核心痛点**：\n"
            "在轮胎车间中，部分基准机台开工极满（单日产出可达 1300 胎），而调机或试产机台可能仅生产 50 胎。"
            "如果直接用**绝对轮胎产量加权**，超大机台即使仅有轻微均值偏离，其负贡献分也会被极度放大，导致系统频繁误报；"
            "反之若**完全不考虑产量（等权）**，又会把 5 胎试验品的小瑕疵等同于批量质量事故。\n\n"
            "**系统设计的平方根平滑公式**：\n"
            "$$\\text{ImpactScore} = \\text{Contribution} \\times \\frac{\\sqrt{N_{\\text{mach}}}}{\\sum \\sqrt{N_{\\text{mach}}}}$$\n\n"
            "**效果与验证**：\n"
            "- 原始 1300 胎与 50 胎的产量悬殊为 **26 倍**；\n"
            "- 经过平方根亚线性压缩后，权重差距收敛至 **5.1 倍**；\n"
            "- 成功消除了高产大设备“替人背黑锅”的现象，真实劣质机台（如 CU621）精准登顶 1 号红色预警。\n\n"
            "*源码位置*：`backend/services/machine_service.py:L825-851`"
        )

    # 2. 询问 CGRS / 调参 / 因果分析 / 路径拆分 / 样本失衡
    if any(k in q for k in ["cgrs", "调参", "路径拆分", "失衡", "因果", "受控", "推荐"]):
        return (
            "### CGRS 调参因果回溯与路径拆分引擎\n\n"
            "**四大核心控制变量铁律**：\n"
            "1. **工序受控路径拆分**：\n"
            "   轮胎受成型、硫化、终检共同影响。分析成型机调参时，必须固定下游硫化机与终检机（例如将 `TB254 -> CU621 -> TU05` 锁定为唯一观察路径），排除下游机台波动对调参因果结论的污染。\n"
            "2. **双侧最低门槛约束**：\n"
            "   单条受控路径改前与改后必须同时满足：$N_{\\text{before}} \\ge 5$ 且 $N_{\\text{after}} \\ge 5$。\n"
            "3. **2.5 倍样本失衡整条剔除**：\n"
            "   $$\\text{Ratio} = \\frac{\\max(N_{\\text{before}}, N_{\\text{after}})}{\\min(N_{\\text{before}}, N_{\\text{after}})} \\le 2.5$$\n"
            "   若样本比值超过 2.5（如改前 20 胎，改后仅 5 胎），方差不可比，系统直接将整条路径剔除，绝不强行对比！\n"
            "4. **自然日严格隔离 (`is_same_day`)**：\n"
            "   彻底修复了早期跨日调参被错误截断导致改前样本为 0 胎的缺陷。\n\n"
            "*源码位置*：`backend/services/cgrs_service.py:L210-380`"
        )

    # 3. 询问 CPK / 指标 / RFPP / CONY / 规格公差
    if any(k in q for k in ["cpk", "rfpp", "cony", "指标", "公差", "usl", "lsl", "均匀性", "动平衡"]):
        return (
            "### 17 项质检指标统一定义与标准 CPK 计算引擎\n\n"
            "**1. 单双侧公式标准纯函数**：\n"
            "- **单侧上限指标 (RFPP, LFPP, TBUL, TBALW 等 15 项)**：\n"
            "  $$C_{pk} = \\frac{USL - \\mu}{3\\sigma}$$\n"
            "- **双侧公差指标 (CONY, PLYSTEER 2 项)**：\n"
            "  $$C_{pk} = \\min\\left(\\frac{USL - \\mu}{3\\sigma},\\; \\frac{\\mu - LSL}{3\\sigma}\\right)$$\n"
            "  其中 $\\sigma$ 采用无偏样本标准差：$\\sqrt{\\frac{1}{N-1}\\sum(x_i-\\mu)^2}$。\n\n"
            "**2. 配方公差 100% 严格遵循准则**：\n"
            "- 指标上限/下限必须严格来自 `Recipes.csv`。\n"
            "- 若未配置公差限值，系统直接返回 `None` 且不计入加权，**坚决不人工硬编码任何假公差**！\n\n"
            "**3. 8小时班次偏移**：\n"
            "- 工厂排产班次日以 `08:00` 为界，`tu_first_shift_date` 统一由 `tu_first_loc_timestamp - 8小时` 计算派生。\n\n"
            "*源码位置*：`backend/core/cpk.py`, `backend/core/indicators.py`"
        )

    # 4. 询问 DuckDB / 内存 / OOM / 溢出盘 / 水位线
    if any(k in q for k in ["duckdb", "oom", "内存", "水位线", "parquet", "溢出", "4gb"]):
        return (
            "### DuckDB 内存保护与 ETL 流式引擎规范\n\n"
            "**1. 安全水位线增量机制 (Safe Watermark)**：\n"
            "- 依据本地现有 Parquet 的最大时间戳，**安全回退 1 天**抽取：\n"
            "  `safe_watermark = max_loc_timestamp - INTERVAL '1 day'`；\n"
            "- 彻底杜绝了夜班交接延迟下线胎与返工复检胎的漏单现象。\n\n"
            "**2. 4GB Out-of-Core 内存溢出保护**：\n"
            "```python\n"
            "con.execute(\"PRAGMA max_memory='4GB'\")\n"
            "con.execute(f\"PRAGMA temp_directory='{temp_dir_sql}'\")\n"
            "con.execute(\"PRAGMA threads=4\")\n"
            "```\n"
            "- 锁定工作集上限为 4GB，多表关联或大批量分组超出内存时，自动下刷至 `duckdb_tmp` 临时磁盘，保护主机操作系统绝对稳定。\n\n"
            "*源码位置*：`backend/etl/clean_data.py`, `backend/core/db.py`"
        )

    # 5. 询问 部署 / 排错 / 服务器 / 红线
    if any(k in q for k in ["部署", "排错", "服务器", "红线", "sop", "10.246.97.159"]):
        return (
            "### 局域网服务器部署规范与防劣红线\n\n"
            "**1. 一键部署流程**：\n"
            "- 双击运行根目录下 `一键部署到服务器.bat` (执行 `deploy_to_server.py`)；\n"
            "- 自动完成：前端 `npm run build` 混淆打包 -> SMB 同步至 `\\\\10.246.97.159\\tu ai\\TireWeight_Uniformity_Analysis` -> 触发远端 NSSM 服务热重启 -> 探针轮询健康确认。\n\n"
            "**2. 架构四大防劣铁律 (绝对禁止违背)**：\n"
            "1. **严禁人工伪造公差限值**：无公差者不计算，绝不设假默认值；\n"
            "2. **严禁跨工段跨分期推荐**：成型设备只跟成型比，硫化只跟硫化比，三期严禁与四期混选；\n"
            "3. **严禁未来数据时间穿越**：历史计算严格锁定 `[target_date - 30天, target_date]`；\n"
            "4. **严禁核心层反向依赖**：`backend/core/` 严禁反向 import `backend/services/`。\n\n"
            "*源码位置*：`deploy_to_server.py`, `docs/wiki/07_devops_and_troubleshooting.md`"
        )

    # 6. 基于当前阅读章节智能概述
    doc_summary_map = {
        "01_system_architecture": "本章重点阐述六层高内聚分层架构、FastAPI装配器设计模式，以及严格的核心层单向依赖铁律。",
        "02_data_sources_and_er": "本章重点阐述 Amazon Redshift 宽表、MES CGRS 库、Recipes 配方表结构，以及 13 道工序单胎条码流转血缘。",
        "03_etl_pipeline_and_engine": "本章重点阐述安全水位线（回退1天防漏单）和 DuckDB 4GB 限制防 OOM 内存保护策略。",
        "04_metrics_and_standard_cpk": "本章重点阐述全厂 17 项质检指标的量纲换算、单双侧标准 CPK 纯函数，以及 8 小时班次偏移计算逻辑。",
        "05_core_algorithms_deepdive": "本章深入讲解产量平方根平滑（消除开满机台替人背黑锅）、三级状态预警瀑布流与 CGRS 路径拆分因果模型。",
        "06_frontend_dashboard_views": "本章重点解析前端四阶漏斗式视觉流向、Pinia 统一状态流转链，以及 ECharts 内存泄漏防护机制。",
        "07_devops_and_troubleshooting": "本章系统梳理局域网共享服务器部署架构、四大疑难故障排查速查表，以及禁止违背的防劣铁律红线。"
    }

    chapter_hint = ""
    if current_doc_id and current_doc_id in doc_summary_map:
        chapter_hint = f"\n\n> 您当前正在浏览 **{current_doc_id}**。\n> {doc_summary_map[current_doc_id]}"

    return (
        f"我是针对 **智能分析系统技术文档** 定制的技术交接 AI 助手。\n\n"
        f"您可以向我询问：\n"
        f"1. **核心算法推导**：如产量平方根平滑公式（消除大产量替人背黑锅）、StableScore 规格评分；\n"
        f"2. **CGRS 工艺分析**：如为什么路径拆分必须满足 $N\\ge 5$ 且样本失衡比 $\\le 2.5$；\n"
        f"3. **指标与公差**：如 RFPP 单侧上限与 CONY 双侧公差 CPK 纯函数实现；\n"
        f"4. **运维与排错**：如 DuckDB 内存溢出解决方案、服务器部署与防劣红线守则。"
        f"{chapter_hint}\n\n"
        f"*提示：当前为内置工业知识引擎即时回答。如需开放式多轮对话，可在右上角设置中配置外部 LLM API Key（支持 DeepSeek / OpenAI / Ollama / Gemini）。*"
    )


@router.post("/wiki/ai-chat")
def ai_chat_endpoint(payload: dict = Body(...)):
    """
    AI 智能技术问答 API
    入参：message (提问文本), doc_id (当前章节), history (可选历史多轮对话)
    """
    user_message = payload.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="提问内容不能为空 (message is required)")

    doc_id = payload.get("doc_id", "01_system_architecture")
    history = payload.get("history", [])

    cfg = _get_ai_config()
    provider = cfg.get("provider", "builtin")
    api_key = cfg.get("api_key", "").strip()

    # 组装上下文知识
    doc_context = ""
    target_file = _safe_doc_path(doc_id)
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                doc_context = f.read()[:4000] # 截取当前文档核心段落
        except Exception:
            pass

    system_prompt = (
        "你是轮胎制造工业质量分析系统 (Tire Weight & Uniformity Analysis & CPK Diagnostics) 的高级技术交接架构师。"
        "你精通全厂17项指标 (RFPP, CONY, TBUL, TBALW)、标准CPK纯函数计算、产量平方根平滑算法 (√N消除替人背黑锅)、"
        "CGRS调参因果回溯路径拆分 (N>=5, 失衡比<=2.5)、DuckDB 4GB内存流式清洗、局域网部署与四大防劣红线。\n\n"
        f"当前用户正在研读章节 [{doc_id}] 的文档内容：\n```markdown\n{doc_context}\n```\n"
        "请结合文档中的精确公式、字段字典与架构规范，用极简、准确、专业的 Markdown 语言回答用户的问题。"
    )

    # 1. 若配置了外部大模型服务且密钥有效，优先调用外部模型
    if provider in ["openai_compatible", "openai", "deepseek", "ollama"] and (api_key or "localhost" in cfg.get("base_url", "")):
        try:
            reply = _call_openai_compatible_api(
                base_url=cfg.get("base_url", "https://api.openai.com/v1"),
                api_key=api_key,
                model=cfg.get("model", "gpt-4o-mini"),
                system_prompt=system_prompt,
                user_message=user_message,
                history=history
            )
            return {
                "status": "success",
                "source": "llm",
                "provider": provider,
                "model": cfg.get("model"),
                "reply": reply,
                "doc_id": doc_id
            }
        except Exception as e:
            # 外部模型超时或失败时无缝降级为内置引擎
            reply = _builtin_knowledge_qa(user_message, doc_id)
            return {
                "status": "success",
                "source": "builtin_fallback",
                "fallback_reason": f"外部模型调用异常 ({str(e)})，已自动切换为内置知识引擎",
                "reply": reply,
                "doc_id": doc_id
            }

    elif provider == "gemini" and api_key:
        try:
            reply = _call_gemini_api(
                api_key=api_key,
                model=cfg.get("model", "gemini-1.5-flash"),
                system_prompt=system_prompt,
                user_message=user_message,
                history=history
            )
            return {
                "status": "success",
                "source": "gemini",
                "model": cfg.get("model"),
                "reply": reply,
                "doc_id": doc_id
            }
        except Exception as e:
            reply = _builtin_knowledge_qa(user_message, doc_id)
            return {
                "status": "success",
                "source": "builtin_fallback",
                "fallback_reason": f"Gemini 接口调用异常 ({str(e)})，已自动切换为内置知识引擎",
                "reply": reply,
                "doc_id": doc_id
            }

    # 2. 默认使用本地高精度工业知识图谱问答引擎
    reply = _builtin_knowledge_qa(user_message, doc_id)
    return {
        "status": "success",
        "source": "builtin",
        "reply": reply,
        "doc_id": doc_id
    }
