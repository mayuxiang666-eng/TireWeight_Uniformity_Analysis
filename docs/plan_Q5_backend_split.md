# Q5 后端按业务域拆分 —— 执行计划 + 修改记录

> 状态：**计划待审阅**（未开始改代码）
> 目标：把 6970 行 / 30 个接口 / 48 个顶层函数的 `backend/main.py`，按业务域拆分成 `core` + `routers` + `services` 三层包，保持 `uvicorn.run("backend.main:app")` 入口与所有 API 路径不变。
> 本文同时作为 Q5 的修改记录（change log），执行时逐条登记。

---

## 0. 现状盘点（已完成，基于精确依赖分析）

| 维度 | 数量 |
|---|---|
| 文件总行数 | 6970 行 |
| 活跃接口 | 30 个（其中 1 个 GET+POST 复用、1 个路由重复注册） |
| 顶层函数 | 48 个 |
| 超长函数 | 18 个（100–700+ 行） |
| 共享辅助被复用 | `qry`(28)、`calc_cpk`(17)、`get_spec_limits`(14)、`sanitize_data`(13) |
| 注释死代码 | 约 1200 行 |

### 必须保留的入口与部署约定
1. `backend/run_server.py` 用 `uvicorn.run("backend.main:app")` —— **入口字符串不能变**。
2. `main.py` 末尾 `uvicorn.run("main:app")`（本地模式）——拆分后可保留或调整。
3. 前端静态托管 `app.mount("/", ...)` 在 main.py 末尾，须保持（且在最后注册，避免挡 /api）。
4. 部署脚本 `deploy_to_server.py`、`scripts/*.bat` 引用 `backend.main` 或 `run_server.py`——不能破坏。

### 拆分前必须注意的既有问题（不在 Q5 范围但需记录）
- **运行时 BUG**：`get_param_recommendation`（/api/cgrs/param-recommendation，main.py:6065）调用了未定义的 `_get_same_section_machines`、`_find_best_event_for_machines`，**该接口当前必然 NameError**。拆分时顺势修复或标注。
- **路由重复注册**：`/api/etl/reload` 被 `handle_etl_reload`(212) 和 `reload_etl_data`(1589) 同时注册，前者遮蔽后者。拆分时清理为一个。
- **`__file__` 依赖**：`get_cleaned_data_path()`/`get_cgrs_data_path()`/`FRONTEND_DIST` 均依赖 `__file__` 定位。拆包后 `__file__` 变化，**必须改为基于 `backend/` 包根的稳定定位**，否则数据文件与前端静态文件全部找不到。这是拆分最大风险点。

---

## 1. 目标结构（按业务域）

```
backend/
├── main.py                  # 装配层：创建 app、加 CORS、挂载所有 routers、静态托管、本地启动（变薄，约 60 行）
├── run_server.py            # 不动
├── core/                    # 共享基础设施（无业务域，所有模块可 import）
│   ├── __init__.py
│   ├── db.py                # db_conn、DATA_PATH、CACHED_ROW_COUNT、reload_duckdb_data、qry、get_cleaned_data_path、get_cgrs_data_path（含 `__file__` 稳定化）
│   ├── calc.py              # calc_cpk、get_spec_usl、get_spec_limits、sanitize_data、aggregate_node_stats_py
│   └── helpers.py           # build_production_time_where、get_phase_sql_condition、get_periods、FRONTEND_DIST 定位
├── routers/                 # 纯接口层（薄）：参数校验 + 调 service + 返回
│   ├── __init__.py
│   ├── articles.py          # /api/articles/* + /api/article/phase
│   ├── machines.py          # /api/machines/*
│   ├── cgrs.py              # /api/cgrs/*
│   ├── filters_trend.py     # /api/filters/* + /api/trend/cpk
│   └── etl_system.py        # /api/etl/* + /api/system/* + /
└── services/                # 业务逻辑（跨域共享的复杂度集中地）
    ├── __init__.py
    ├── article_service.py   # get_all_articles、get_articles_warning_cpk、get_article_barcode_measurements、get_article_lot_cpk_trend、get_lot_barcode_detail、get_article_phase
    ├── machine_service.py   # get_machines_cpk、get_machine_cpk_trend、get_machine_combination_tree、get_machine_process_sankey、get_machine_best_process_sankey、get_best_tu_machine_for_spec、get_top_warning_machines、calculate_critical_machine、get_spec_warning_machines_detailed、get_machine_cpk_trend_comparison、compute_machine_all_weighted_cpk
    ├── cgrs_service.py      # get_cgrs_records、compute_cgrs_controlled_analysis_data、calculate_cgrs_cpk_comparison、get_param_recommendation、get_cgrs_recommended_params、缓存三件套
    └── trend_service.py     # get_cpk_trend
```

### 接口归属总表（30 个）
| 路由 | 归属文件 |
|---|---|
| `/` | routers/etl_system.py |
| `/api/etl/reload` (GET+POST) | routers/etl_system.py |
| `/api/etl/status` | routers/etl_system.py |
| `/api/system/restart` (GET+POST) | routers/etl_system.py |
| `/api/article/phase` | routers/articles.py |
| `/api/articles/all` | routers/articles.py |
| `/api/articles/warning-cpk` | routers/articles.py |
| `/api/articles/barcode-measurements` | routers/articles.py |
| `/api/articles/lot-cpk-trend` | routers/articles.py |
| `/api/articles/lot-barcode-detail` | routers/articles.py |
| `/api/cgrs/records` | routers/cgrs.py |
| `/api/cgrs/controlled-analysis` | routers/cgrs.py |
| `/api/cgrs/param-recommendation` | routers/cgrs.py |
| `/api/cgrs/recommended-params` | routers/cgrs.py |
| `/api/machines/cpk` | routers/machines.py |
| `/api/machines/cpk/trend` | routers/machines.py |
| `/api/machines/combination-tree` | routers/machines.py |
| `/api/machines/process-sankey` | routers/machines.py |
| `/api/machines/best-process-sankey` | routers/machines.py |
| `/api/machines/top-warning` | routers/machines.py |
| `/api/machines/best-tu` | routers/machines.py |
| `/api/machines/cpk-trend-comparison` | routers/machines.py |
| `/api/filters/articles` | routers/filters_trend.py |
| `/api/filters/daterange` | routers/filters_trend.py |
| `/api/trend/cpk` | routers/filters_trend.py |

---

## 2. 关键实现细节

### 2.1 db.py —— 共享连接与数据加载（拆分最大风险点）
- 把 `db_conn`、`DATA_PATH`、`CACHED_ROW_COUNT` 及 `reload_duckdb_data/qry` 移入 `core/db.py`。
- **修复 `__file__`**：用基于 `backend/` 目录的绝对锚点 `_CORE_DIR = os.path.dirname(os.path.abspath(__file__))`（= backend/），数据候选路径从 `_CORE_DIR/data`、`os.path.dirname(_CORE_DIR)/data`、`_CORE_DIR/../data` 等推导，与原 get_cleaned_data_path 的 6 个候选语义一致。CGRS 同理。
- 保持"import 即初始化"的副作用：`core/db.py` 顶层执行 `DATA_PATH = get_cleaned_data_path(); db_conn = duckdb.connect(":memory:"); reload_duckdb_data()` —— 这样所有 router 首次 import 时数据库已就绪，行为与原 main.py 一致。
- `get_article_phase_endpoint` 自己 `duckdb.connect()` 的独立连接保持不动（它是读文件快照，不依赖 db_conn）。

### 2.2 calc.py —— 纯计算常量
- `calc_cpk`、`get_spec_usl`、`get_spec_limits`、`sanitize_data`、`aggregate_node_stats_py` 全是纯函数，移入 `core/calc.py`（注意 `get_spec_usl/get_spec_limits` 依赖 `qry` → 从 `core/db` import，无循环：db 不 import calc）。

### 2.3 helpers.py —— SQL 条件构建与路径
- `build_production_time_where`、`get_phase_sql_condition`、`get_periods`、`FRONTEND_DIST` 定位逻辑放这里。
- `get_periods` 依赖 `qry` → import `core.db`。

### 2.4 services —— 业务逻辑
- 每个 service 文件内放对应接口的业务函数（原样移动，函数体不改）。
- 跨域共享函数放对位置：
  - `calculate_cgrs_cpk_comparison` / `compute_cgrs_controlled_analysis_data` → `cgrs_service.py`（articles/machines 需要时从 cgrs_service import）
  - `get_top_warning_machines` / `get_best_tu_machine_for_spec` / `get_spec_warning_machines_detailed` / `calculate_critical_machine` → `machine_service.py`
  - `compute_machine_all_weighted_cpk`（死代码，无调用）→ 放入 machine_service.py 或按旧计划标记删除

### 2.5 routers —— 薄路由
- 每个 router 文件定义 `router = APIRouter()`，用 `@router.get(...)` / `@router.post(...)` 替代 `@app.get`。
- **路由路径不变**（前缀由 router 声明或逐条写全）。
- 建议：router 文件里 `router = APIRouter(prefix="/api")`，然后 `@router.get("/articles/all")` 等（路径保持原样，避免逐条拼前缀出错）。

### 2.6 main.py —— 变薄
```python
# main.py（装配层）
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.db import db_conn  # noqa: F401  （触发初始化）
from core.helpers import FRONTEND_DIST
from routers import articles, cgrs, machines, filters_trend, etl_system

app = FastAPI(title="轮胎质量分析看板 API", version="1.1.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

app.include_router(articles.router)
app.include_router(machines.router)
app.include_router(cgrs.router)
app.include_router(filters_trend.router)
app.include_router(etl_system.router)

from fastapi.staticfiles import StaticFiles
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
```
- **注意 import 顺序**：先 import routers（触发 db 初始化），再建 app；或先在 core.db import 时触发初始化。重要的是保证 `import backend.main` 之后 `qry` 可用。
- `run_server.py` 的 `uvicorn.run("backend.main:app")` **不变**。

---

## 3. 顺带修复/清理项（需你确认是否一并做）

| 项 | 内容 | 影响 |
|---|---|---|
| A | `get_param_recommendation` 未定义函数引用 —— 若前端在用，需补实现；若不用，标注死代码或注释 | 风险：无法评估业务语义，我建议先注释掉该分支并让接口返回友好提示，或你确认后处理 |
| B | `/api/etl/reload` 重复注册 → 合并为一个 handler | 无行为变化（后者本来被遮蔽） |
| C | 约 1200 行注释死代码（1639-1818、2510-2534、5033-5640）→ 拆分时干脆不搬，直接丢弃 | 减少体积；无行为影响 |

> **建议**：B 直接做；C 直接做；A 单独决策。

---

## 4. 执行顺序（每步可回归）

1. **建包骨架**：`backend/core/`、`backend/routers/`、`backend/services/`，各放 `__init__.py`。
2. **core/db.py**：先移动并稳定化 `__file__` 定位。此时 main.py 暂用 `from core.db import *` 验证加载成功。
3. **core/calc.py、core/helpers.py**：移动纯函数。
4. **services 各文件**：移动业务函数（原样搬，不改逻辑）。
5. **routers 各文件**：建薄路由。
6. **重写 main.py** 为装配层。
7. **全量验证**（见 §5）。
8. 清点 `__pycache__` 与旧引用，确认无 `from main import` 残留。

## 5. 验收标准

1. `python -m py_compile backend/core/*.py backend/routers/*.py backend/services/*.py backend/main.py` 全部通过。
2. **从根目录**：`python -c "from backend.main import app"` 成功（不报错、能 import）。
3. **从 backend 目录**：`python -c "from main import app"` 成功（本地模式）。
4. 启动 `uvicorn backend.main:app --port 8000`，**抓取全部 30 个活跃接口**：任意抽样 5 个（articles/warning-cpk、machines/cpk、machines/combination-tree、cgrs/records、trend/cpk）响应结构/状态码与拆分前一致。
5. `npm run build` 前端无需改动（验证 API 路径未变——前端代码不依赖后端文件结构，本项仅确认无意外）。
6. **部署兼容**：`run_server.py` 未改；`deploy_to_server.py`/`scripts/*.bat` 引用的路径仍有效。
7. 数据库加载副作用正确：import 即加载、`/api/etl/reload` 后可重载（GET+POST 均可用）。
8. `app.routes` 中活跃路由数与拆分前一致（30 条 + 静态 mount + docs）。

---

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| `__file__` 路径全崩（数据/前端文件找不到） | 用包根锚点 `Path(__file__).resolve().parent` 替代 `os.path.dirname(__file__)`；对照原候选路径逐一验证候选文件存在 |
| 循环 import（calc ↔ db ↔ helpers） | 严格单向依赖：db / calc / helpers 互不依赖；services → core；routers → services + core |
| import 副作用重复执行（db 初始化执行多次） | db.py 顶层初始化仅执行一次（模块缓存保证）；main.py 只 import 一次 |
| 路由前缀写错导致 404 | router 用 `prefix="/api"`，路径与装饰器原样核对表逐个比对 |
| 部署脚本依赖 main.py 相对路径 | 不改 run_server.py；main.py 仍存在（只是变薄） |

**回滚**：拆分 = 移动+新建文件，main.py 仍保留精简版。回滚 = 用 git revert 恢复原 main.py 并删除新增包。无数据/schema 变更。

---

## 7. 修改记录（执行时逐条填写）

| 日期 | 文件 | 动作 | 验证结果 |
|---|---|---|---|
| （待执行） | core/db.py | 新建：db_conn/qry/reload/路径稳定化 | |
| （待执行） | core/calc.py | 新建：calc_cpk/spec_limits/sanitize | |
| （待执行） | core/helpers.py | 新建：SQL条件/periods/FRONTEND_DIST | |
| （待执行） | services/*.py | 新建：业务函数原样迁移 | |
| （待执行） | routers/*.py | 新建：薄路由，路径不变 | |
| （待执行） | main.py | 重写为装配层 | |
| （待执行） | 清理项 B | /api/etl/reload 去重 | |
| （待执行） | 清理项 C | 丢弃 1200 行注释死代码 | |

---

## 8. 待你确认
1. 上述 **core / routers / services 三层结构**是否认可？（或希望更扁平的"仅 routers + core"两层？）
2. **顺带清理项 A**（param-recommendation 未定义函数）如何处理：注释该分支 / 保留现状 / 你告诉我该功能预期？
3. **顺带清理 B / C** 是否一并做？
4. 拆分是否包含删除 `compute_machine_all_weighted_cpk`（死代码）？