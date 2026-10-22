# 01. 系统全景架构与工程规范

---

## 1. 系统定位与核心业务目标

本项目为**轮胎生产质量数据分析与可视化诊断系统 (Tire Weight & Uniformity Analysis & Cpk Diagnostics System)**。
在轮胎高端制造中，轮胎的**重量 (Weight)**、**均匀性 (Uniformity，如 RFPP/LFPP/CONY 等力学波动)**、**动平衡 (Dynamic Balance)** 及**几何跳动 (Geometry)** 是决定整车高速行驶安全性、颠簸感与静音性的绝对核心指标。

```mermaid
graph LR
    subgraph P_Core ["制造核心痛点"]
        P1["高维指标多达 17 项"]
        P2["工序跨越 13 道环节"]
        P3["独占开满机台掩盖元凶"]
        P4["盲目调参导致质量反向恶化"]
    end
    
    subgraph S_Empower ["诊断系统赋能"]
        S1["全厂 17 项指标 CPK 实时监控"]
        S2["全流程变异流向桑基图"]
        S3["产量平方根平滑机台精准归因"]
        S4["CGRS 调参因果回溯与智能推荐"]
    end
    
    P1 --> S1
    P2 --> S2
    P3 --> S3
    P4 --> S4
```

系统核心解决四大业务痛点：
1. **指标统一监控**：统一全厂 17 项检测指标的配方公差、标称量纲，实时呈现全厂/规格加权 CPK 与 SPC 控制限；
2. **全流程穿透溯源**：打通从原材料、半部件批次 (Lot)、成型 (GT)、硫化 (CT) 到终检 (TU) 的完整时序血缘；
3. **精准瓶颈定位**：利用**产量平方根平滑算法**消除超大产量机台的“替人背黑锅”效应，揪出真实劣化设备；
4. **闭环工艺干预**：结合 Continental MES CGRS 调参变动日志，回溯工艺修改效果，为车间工程师提供高置信度的参数优化建议。

---

## 2. 全栈技术选型与运行环境

| 分层 | 技术选型 | 版本/组件要求 | 核心职能 |
| :--- | :--- | :--- | :--- |
| **前端应用** | Vue 3 + Vite | Vue 3.4+ (Composition API / Setup) | 现代化响应式组件化架构 |
| **UI 视图库** | Element Plus | 2.6+ (暗黑/微立体质感定制) | 统一规范的对话框、表格、徽章、工具栏 |
| **可视化图表**| ECharts 5 | 5.5+ (vue-echarts 封装) | 桑基图 (Sankey)、双轴趋势图、树图 (Tree) |
| **状态流转** | Pinia | 2.1+ | 全局响应式状态机 (`filterStore`) |
| **后端服务** | Python FastAPI | FastAPI 0.100+, Uvicorn 0.22+ | 高性能异步 ASGI 接口服务与路由装配 |
| **分析计算引擎**| DuckDB | DuckDB 0.9.2+ (常驻内存 + 临时盘) | 亿级列存 Parquet 极速流式聚合与 Out-of-Core 计算 |
| **数据科学工具**| Pandas, NumPy | Pandas 2.0+, NumPy 1.24+ | 时序补齐、统计学方差/分位数/矩阵运算 |
| **上游连接** | psycopg2 / pyodbc | Redshift PostgreSQL 驱动, ODBC SQL Server | 跨库自动化 ETL 增量拉取 |

---

## 3. 六层架构拓扑与数据流向

整个工程代码严格遵循六层高内聚分层设计：

```mermaid
graph TD
    subgraph S1 ["1. 物理数据层 (Data Storage)"]
        DS1["Amazon Redshift: yield_flat_table"]
        DS2["Continental MES CGRS: SQL Server"]
        DS3["本地 Recipes.csv: 标准配方公差"]
    end

    subgraph S2 ["2. ETL 流式管道 (Data Pipeline)"]
        ETL1["fetch_data.py 安全水位线抽取"]
        ETL2["clean_data.py DuckDB 内存流式清洗"]
        ETL3["yield_flat_table_joined_100_cleaned.parquet"]
        DS1 & DS2 & DS3 --> ETL1 --> ETL2 --> ETL3
    end

    subgraph S3 ["3. 计算核心与数据常驻层 (Core Layer)"]
        C1["backend/core/db.py DuckDB 常驻内存表 clean_yield"]
        C2["backend/core/cpk.py 17项标准 CPK 纯函数"]
        C3["backend/core/time_utils.py 8小时班次偏移与期别缓存"]
        ETL3 --> C1
        C1 --> C2 & C3
    end

    subgraph S4 ["4. 业务服务组合层 (Service Layer)"]
        SV1["trend_service.py 加权趋势与不良统计"]
        SV2["article_service.py 核心规格与三级行动表"]
        SV3["machine_service.py 平方根平滑与机台归因"]
        SV4["process_flow_service.py 桑基图与组合树"]
        SV5["cgrs_service.py CGRS 路径拆分与参数推荐"]
        C2 & C3 --> SV1 & SV2 & SV3 & SV4 & SV5
    end

    subgraph S5 ["5. API 适配路由层 (Routing Layer)"]
        R1["backend/routers/trend.py"]
        R2["backend/routers/articles.py"]
        R3["backend/routers/machines.py"]
        R4["backend/routers/cgrs.py"]
        R5["backend/routers/system.py"]
        R6["backend/routers/wiki.py"]
        SV1 & SV2 & SV3 & SV4 & SV5 --> R1 & R2 & R3 & R4 & R5 & R6
    end

    subgraph S6 ["6. 前端可视化呈现 (Presentation Layer)"]
        UI["src/views/Dashboard.vue 大屏监控与决策看板"]
        WIKI["docs/wiki.html 交互式思维导图与技术 Wiki"]
        R1 & R2 & R3 & R4 & R5 & R6 --> UI & WIKI
    end
```

---

## 4. 依赖隔离铁律与服务解耦注入机制

为彻底杜绝 Python 大项目中常见的“循环导入 (Circular Import)”与“偶合灾难”，工程制定了三项刚性架构原则：

### 4.1 核心层单向依赖原则 (Strict Downward Imports)
* `backend/core/` 目录下的纯函数工具（`cpk.py`, `indicators.py`, `db.py`, `time_utils.py`）**绝对严禁反向 import `backend/services/`**。
* 核心层函数必须保持为**确定性纯函数 (Pure Functions)**，仅接收入参并返回计算结果。

### 4.2 跨服务运行时动态依赖注入 (Runtime Helper Injection)
* 当 `article_service.py` 需要调用 `machine_service.py` 的机台预警算法，或 `process_flow_service.py` 需要调用 `cgrs_service.py` 的调参对比时，**禁止在文件顶部互相静态 import**。
* 统一采用**延迟解析钩子或动态注入**模式：

```python
# 代码位置：backend/services/article_service.py:L24-67
_top_warning_provider = None
_best_tu_provider = None
_cgrs_cpk_comparator = None

def _get_top_warning_provider():
    global _top_warning_provider
    if _top_warning_provider is None:
        try:
            from backend.services.machine_service import get_top_warning_machines
            _top_warning_provider = get_top_warning_machines
        except Exception:
            pass
    return _top_warning_provider
```

### 4.3 路由控制层精简化 (< 80 行装配)
* `backend/main.py` 严格保持为精简装配器，仅负责中间件挂载、全局常驻连接初始化与子路由聚合，禁止编写具体业务 SQL 或复杂清洗逻辑。

---

> [!TIP]
> **下一章导航**：
> 了解了整体架构后，请阅读 [02. 全流程数据源与实体关系拓扑](02_data_sources_and_er.md)，深入掌握三大物理数据源结构与 13 道工序数据字典。
