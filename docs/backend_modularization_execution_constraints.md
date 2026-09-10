# 后端模块化重构 · 执行约束与阶段门禁规范 (Execution Constraints & Stage Gates)

> **文件属性**：执行规则规范 (Execution Rule Specification)  
> **配套文档**：`docs/backend_modularization_architecture_plan.md`（技术方案，唯一架构依据）  
> **适用范围**：任何接管本次后端重构代码修改任务的执行 Agent  
> **文档目标**：约束执行 Agent 必须真实、完整、逐字节地落实方案，禁止偷懒、简写、占位或偏离；并强制分阶段修改、每阶段验证通过后才能进入下一阶段。

---

## 0. 总则（铁律，违反即视为任务失败）

1. **方案文档是唯一架构依据**：一切代码结构、文件归属、函数签名、目录层级以 `backend_modularization_architecture_plan.md` 为准。执行 Agent 不得自行增减模块、合并文件、改函数名、改签名。
2. **逻辑零改动是最高优先级**：本重构是"搬家"不是"重写"。除方案 §4.3 明确标注的 param-recommendation 补齐修复外，**其余 20 个接口必须在行为上逐字节保真**。
3. **分阶段执行，门禁优先**：严格按阶段 1→2→3→4→5 顺序执行。**每当一个阶段完成，必须执行该阶段门禁验证；门禁全部通过后才允许进入下一阶段**。禁止跨阶段连续修改后再一次性验证。
4. **禁偷懒三连**：禁止「伪迁移」、禁止「简化重写」、禁止「占位符」（`# TODO` / `pass` / 空实现 / `NotImplementedError` 一律不允许出现在产出代码中）。
5. **宁慢勿错**：所有迁移必须提供"迁移凭证"（见 §6），证明函数是从原文件逐字节搬出，而非凭记忆重打。

---

## 1. 禁止行为清单（Hard Blacklist）

| # | 禁止行为 | 说明 |
|---|---|---|
| B1 | 不读原文件就写新文件 | 每个迁移候选函数，必须先 `Read`/`Grep` 原 `backend/main.py` 目标行号区域，完整读取后再搬迁 |
| B2 | 重新实现/简化 SQL | SQL 必须**原样复制**。禁止改写 WHERE 拼法、GROUP BY、CASE 分支、子查询、`COALESCE`、`*10.0` 等 |
| B3 | 用配置/字典替代原函数逻辑 | 方案中 `core/indicators.py` 的 `_lookup_spec_usl` 等处，文档已声明"必须从 `get_spec_usl`(main.py:405) 原样复制"，禁止用文档示意代码替代真实 SQL |
| B4 | 改动返回值结构/字段名/默认参数 | 所有 Query 参数名、默认值、`status`/`data`/`message` JSON 字段、排序规则、`round(x, n)` 精度必须与现状一致 |
| B5 | 删除未列入清理清单的代码 | 只允许删除方案明确标注的死代码；不确定的代码一律搬走并保留 |
| B6 | 新增依赖/第三方库 | 禁止 pip install 新包；只允许项目已有依赖 |
| B7 | 修改前端任何文件 | 前端 `src/` 本次重构不涉及；`param-recommendation` 补齐只需后端按既有协议返回，前端不动 |
| B8 | 修改 `run_server.py` / 部署脚本 | `uvicorn.run("backend.main:app")` 入口、NSSM、`deploy_to_server.py` 白名单除外（§7 阶段4 允许更新白名单） |
| B9 | 加线程锁 / 缓存 / 防御性改动 | `qry()` 遵用户指示**不加锁**；TTL 缓存只允许原样迁移到 `core/cache_utils.py` |
| B10 | 跳过门禁直接开始下一阶段 | 违反 §3，直接判任务失败 |

---

## 2. 必守技术红线（实现细节）

1. **`core/cpk.py` 必须从原函数逐字节复制**：`calc_cpk`(515)、`get_spec_usl`(405)、`get_spec_limits`(490) 三个函数体原样搬运，**禁止用 `INDICATOR_CONFIG` 的示意值替代**。方案 §4.1 里的代码块是**设计示意**，不是替代品。
2. **静态托管必须最后注册**：`app.mount("/", StaticFiles(...))` 必须排在所有 `include_router` 之后。
3. **`_recommend_cache_*` 归属 core**：`_recommend_cache_key/get/set`(5098~5108) 迁入 `core/cache_utils.py`，`cgrs_service` 与 `trend_service` 各自 import，禁止服务层互相 import。
4. **`indicators.py` 依赖边界**：仅可 import `core/cpk`、`core/db`；严禁 import 任何 `services/*`。
5. **`param-recommendation` 补齐范围受限**：仅新增缺失的扫描函数（`_get_same_section_machines`/`_find_best_event_for_machines` 或方案 §4.3 的 `recommend_best_for_spec`），补齐依据方案 §4.3 的"强规格锁定 + 两级兜底"铁律，输出协议（`has_recommendation`/`gt_recommendation`/`cu_recommendation`/`scanned_*`/`target_date`）保持不变。**禁止顺带改动其他接口**。
6. **端口与版本号**：`FastAPI(version="1.1.1")` 保持不动；`uvicorn.run` 端口对齐 `run_server.py` 现状。

---

## 3. 分阶段执行与门禁（Gate) 强制流程

> 执行顺序必须线性：**阶段 N 门禁通过 → 阶段 N+1**。任一阶段门禁失败，立即停止，修复到通过为止，禁止带病前进。

```mermaid
graph LR
    S1["阶段1: core/"] -->|G1 门禁| S2["阶段2: services/"]
    S2 -->|G2 门禁| S3["阶段3: routers/"]
    S3 -->|G3 门禁| S4["阶段4: main.py"]
    S4 -->|G4 门禁| S5["阶段5: 全量回归"]
```

### 阶段 1：建立 `backend/core/`
- 产出：`config.py`、`serializer.py`、`cpk.py`、`time_utils.py`、`indicators.py`、`cache_utils.py`、`db.py`。
- 内容来源（main.py 原行号）：`sanitize_data`(26)、`get_cleaned_data_path`(50)、`get_cgrs_data_path`(66)、`reload_duckdb_data`(110)、`build_production_time_where`(170)、`qry`(392)、`get_spec_usl`(405)、`get_spec_limits`(490)、`calc_cpk`(515)、`get_phase_sql_condition`(1491)、`_recommend_cache_*`(5098~5108)。
- ⚠️ 此阶段结束后 main.py 仍包含这些函数，但**已从 main.py 删除**并迁移至 core（由迁移凭证证明）。

### 阶段 2：建立 `backend/services/`
- 产出 5 个服务文件；按方案 §5 映射表搬运函数。此阶段 main.py 中的服务函数删除，改由 services 提供。

### 阶段 3：组装 `backend/routers/`
- 产出 5 个 router 文件；每个路由函数 ≤20 行，仅负责参数提取 → 调 service → 返回。

### 阶段 4：重写 `backend/main.py`
- 装配 5 个 router + CORS + 静态托管；文件 ≤80 行；更新部署白名单。

### 阶段 5：全量回归验证
- 见 §4 验证套件，全部通过才算完成。

---

## 4. 验证门禁清单（每阶段必须全过）

### G-0 通用前置（每阶段开始前确认）
- [ ] 项目可 `python -m py_compile backend/main.py` 通过（作为基线）。
- [ ] 已建立改动前备份（复制原 main.py 到工作区外）。

### G-1~G-4 各阶段通用门禁
1. **语法门禁**：`python -m py_compile <backend 下全部 .py>` 全部通过，零报错、零警告。
2. **导入门禁**：从项目根目录 `python -c "import backend.main"` 成功；从 `backend/` 目录 `python -c "import main"` 成功（双入口兼容）。
3. **无环门禁**：依赖方向必须 `routers → services → indicators → core`，禁止同层/services 间互相 import（grep 校验：services 文件内不得出现 `from backend.services` / `import services`；indicators 内不得出现 `services`）。
4. **路由门禁**：`python -c "from backend.main import app; print(sorted([r.path for r in app.routes if hasattr(r,'path')]))"` 输出与基线一致（27 条路由，无重复、无缺失、无多注册）。
5. **迁移凭证门禁**：§6 要求的新文件函数体与 main.py 原函数体做字符串归一化对比（忽略空白差异），相似度必须 ≥ 99%（差异仅允许 import 头/缩进层级）。
6. **零占位门禁**：对全部新文件 grep `TODO|pass\s*$|NotImplemented|FIXME|placeholder`，结果必须为空。
7. **无死代码回流门禁**：新文件 grep 死代码特征（`api/insights`、`LOT_MAP`、`def get_periods`、`diagnose_machine`、`compute_machine_all_weighted_cpk`），结果必须为空。

### G-5 阶段 5 全量回归（最终验收）
1. 启动服务：`python -m uvicorn backend.main:app --port 8000`（结果：启动成功，DuckDB 表加载正常）。
2. 接口冒烟：对方案 §5 列表的 21 个接口，逐一发起请求并断言 `status == "success"`（param-recommendation 断言 `has_recommendation` 字段存在即可，允许 recommendation 空，但**不得是 error**）。
3. 输出一致校验：用**改动前备份**起一个基线进程，对同一组默认参数请求关键接口（`/api/trend/cpk`、`/api/machines/cpk`、`/api/articles/warning-cpk`、`/api/machines/combination-tree`、`/api/cgrs/controlled-analysis`、`/api/articles/lot-cpk-trend`），新旧两份响应 JSON **逐字段一致**（除 param-recommendation 外）。
4. 前端构建不回归：项目根目录 `npm run build` 通过（仅验证不破坏，不允许改前端文件）。

---

## 5. 每个阶段完成后的交付物

每个阶段结束，执行 Agent **必须**在报告中输出：

| 交付项 | 内容 |
|---|---|
| 迁移凭证 | 函数名 → 原行号 → 新文件/新行号 → 相似度百分比 |
| 门禁结果 | 上述 G-x 清单逐项勾选 + 实际命令输出粘贴 |
| 差异说明 | 任何未照搬的偏差（必须为 0）；若存在，说明原因并请求审查 |
| 已知风险 | 本阶段新暴露的问题、遗留观察项 |

> 若某阶段"迁移凭证"缺失或相似度 < 99%，视为未完成，禁止进入下一阶段。

---

## 6. 迁移凭证的唯一可信制作方法

**不允许**『读一眼、凭记忆重写』。每个函数迁移的可靠流程：

1. 用 `Read`（offset/limit）完整读取 main.py 目标函数体（含装饰器、签名、docstring）。
2. 在目标新文件中写入**逐字复制**的代码，仅允许调整 import 头与缩进层级。
3. 写完后用脚本对比：
   ```
   # 示例（Python）：
   # 提取 main 原函数文本（去掉前导缩进）与 新文件函数文本对比
   归一化空白后 assert 旧体 == 新体
   ```
4. 结果记入 §5 迁移凭证表的"相似度"列。

---

## 7. 回滚规范（若途中不可恢复）

- 任何阶段若连续 3 次门禁失败 / 或引入无法定位的回归，立即**全量回滚**：恢复备份 main.py，删除所有新建目录，回到基线，报告失败原因。
- 禁止在失败状态下"带病推进"或试图临时改需求绕过。

---

## 8. 一键校验脚本（建议执行 Agent 固化）

在项目根目录维护一个临时校验脚本（不入库），串起 G-x 所有断言并输出红/绿报告：

```python
# scripts/refactor_gate.py（示意，执行 Agent 自行实现完整断言）
# 1) py_compile 全部 backend/*.py
# 2) import backend.main / import main 双入口
# 3) 路由集合 diff
# 4) 迁移凭证相似度比对
# 5) TODO/pass 占位扫描
# 6) 死代码回流扫描
```

---

## 9. 最终交付标准

- ✅ `backend/` 目录结构 = 方案 §3 树（15 个文件）。
- ✅ main.py ≤ 80 行且为纯装配。
- ✅ 阶段 5 全部门禁绿。
- ✅ 前端零改动、构建通过。
- ✅ 无占位符、无简化、无死代码回流、无跨服务 import。
- ✅ param-recommendation 由 error 恢复为可返回 normal 响应。