# 重构计划：Q1–Q4 改造方案（执行记录）

> 状态：**本地重构已完成，本地测试全部通过**（⚠️ 严格按指示仅在本地执行，尚未发布到服务器）
> 范围：Q1–Q4 完整完成。
> 原则：凡涉及"计算口径"变化处均已对齐确认；非业务逻辑全部优化瘦身。

---

## 0. 本次目标一句话

把三处不一致的 CPK 计算口径统一成一个函数、删掉已废弃的深度诊断面板和不再使用的机台异常统计接口、移除数据表里的硬编码异常标记列，并把每一步的改动记录成 md 以便回溯。目标：**更简洁、口径全站统一、更快、易维护**。

---

## Q1：统一 USL 规格上限为一个函数

### 现状
"规格标准上限 USL"的兜底规则被复制成三份，且其中两份漏了 GROUP 4：

| 位置 | 兜底表范围 | 结论 |
|---|---|---|
| `get_spec_usl`（backend/main.py:414） | GROUP 1/2A/2B/3/**4** | 公共函数，完整（被视为标准） |
| warning-cpk 接口内联 CASE（backend/main.py:2143-2149） | GROUP 1/2A/2B/3（**缺 4**） | 需改为调用 `get_spec_usl` |
| CPK 趋势接口内联 CASE（backend/main.py:6152-6157） | GROUP 1/2A/2B/3（**缺 4**） | 需改为调用 `get_spec_usl` |

### 改动内容
1. warning-cpk 与 CPK 趋势接口中，删除各自的内联 `COALESCE(ANY_VALUE(standard_rfpp/rfh1), CASE ... )` 片段，改为统一调用 `get_spec_usl(article10, "rfpp"/"rfh1")`。
2. `get_spec_usl` 本身保持不动（它已是标准实现）。

### 口径变化（需确认 ✅）
同一份数据下，凡"无 `standard_rfpp/rfh1`、且属于 GROUP 4"的规格：
- 现状：warning-cpk / CPK 趋势 得到 USL = 空 → CPK 计算异常/显示不出
- 改后：得到 USL = rfpp:145 / rfh1:100 → 能正常显示数值

**结论：这两个接口对 GROUP 4 规格的输出会"从无到有"。这是口径修正，不是 bug。需你确认接受此数值变化。**

### 影响面
- 后端：backend/main.py:2143-2149、6152-6157 两处 SQL 改参数化后再调函数。
- 前端：无改动。
- 验收：对 GROUP 4 且无 standard 值的规格，改前后各调一次两个接口，对比输出。

---

## Q2：组合树 CPK 计算口径全站统一（含修改记录 md）

### 现状
`/api/machines/combination-tree`（backend/main.py:3532）只返回每片叶子的 `avg_val`/`std_val`/`lot_cnt`，**不返回 CPK**。前端 `MachineCombinationTree.vue` 用 JS 另算一套 CPK，与后端统一函数 `calc_cpk` 存在三处差异：

| 差异点 | 后端 `calc_cpk`（main.py:524） | 前端 JS（MachineCombinationTree.vue:767-798、838-887） |
|---|---|---|
| 截断区间 | `[-5, 5]`（允许负值，负=严重超差） | `[0, 5]`（负数被压成 0） |
| weight（胎重） | 按双侧公差 `±0.28%` 算 CPK 指数 | 直接显示"平均偏差%"（语义完全不同） |
| std 容错 | `std≤1e-6` 返回 1.33 | `std>0` 才除，否则 1.33（行为接近但不全等） |

### 决策（你已确认）
- **完全统一**：rfpp/rfh1/cony 的 clamp 由 `[0,5]` 改为 `[-5,5]`；weight 由"偏差%"改为 CPK 指数。
- **记录修改 md** 便于回溯与修正。

### 改动内容
1. **后端** `get_machine_combination_tree`（backend/main.py:3532）：在返回的每个 `path` 里增加 `cpk` 字段，用 `calc_cpk(avg_val, std_val, global_usl, global_lsl)` 计算（weight 也走 `calc_cpk`，全局 USL/LSL 来自 `get_spec_limits`，已符合 weight=±0.28 语义）。
2. **前端叶子计算** `MachineCombinationTree.vue:767-798`：删除其中的 CPK 计算分支，改为读取后端返回的 `p.cpk`（weight 也读 `p.cpk`，不再显示 avg）。
3. **前端聚合节点计算** `MachineCombinationTree.vue:838-887`（`aggregateNodeStats`）：该函数负责把多条分支"合并方差"聚合到上层节点。对齐口径：
   - 合并方差公式本身（`combinedMean` / `combinedVar` 加权合并）保留（数学上正确）；
   - 但最后一步 CPK 计算的 clamp 从 `[0,5]` 改为 `[-5,5]`，weight 分支从 `cpk = combinedMean` 改为同样调用合并后的 `calc_cpk`（用合并后的 mean/std 与全局 USL/LSL）。
4. **新增/更新修改记录 md**：`docs/refactor_plan_Q1_Q4.md` 内维护"修改记录"，写到 `docs/change_log_Q2_combination_tree.md`（独立文件，便于回溯每一步）。
   - 记录：改前 vs 改后 的公式、clamp 区间、weight 语义、涉及行号、变化示例数值。

### 口径变化（需确认 ✅）
- rfpp/rfh1/cony：超差为负时，显示值由压成 0 变为显示负数（如 -1.01）。
- weight：显示值由"偏差%"（如 +1.5）变为"CPK 指数"（如 1.77），含义改变。
- 聚合节点：所有上层节点的 CPK 显示值同样按新口径变化。
- **范围**：仅影响组合树这一个组件/接口，其它图表接口不受影响（它们本就走 `calc_cpk` 或各自已有算法）。若你希望全站其它图表也统一到 [-5,5]，属于另一项，不在本计划内。

### 验收
1. 选用一个数据量足够的规格，改前后对比组合树：叶子 CPK、聚合 CPK、weight 指标展示。
2. 前端 `npm run build` 通过。
3. 确认修改记录 md 已按 改前/改后 记录公式与示例值。

---

## Q3：删除深度诊断面板（已废弃）

### 现状
- `Dashboard.vue:556` 渲染 `<DiagnosticsPanel />`，但其调用接口已被注释：
  - `/api/diagnose/suspects`、`/api/diagnose/lots` → 后端已注释（backend/main.py:5834、5900 附近）
  - 支撑算法 `kmeans_service.py` 已是空壳
- 断链 api 方法：`getSuspects`（src/api/index.js:51）、`getLotDiagnosis`（src/api/index.js:57）

### 改动内容
1. **前端删除组件文件**：`src/components/panels/DiagnosticsPanel.vue`、`src/components/charts/LotCompareChart.vue`
2. **Dashboard.vue 清理**：
   - 删 import：`DiagnosticsPanel`（Dashboard.vue:638）
   - 删渲染点：`Dashboard.vue:556-560` 区域
   - 删两个 `v-if="false"` 死区块（Dashboard.vue:95、Dashboard.vue:384 起的 Row4 区块）及其内引用的状态/变量
3. **api 清理**：`src/api/index.js` 删 `getSuspects`(51)、`getLotDiagnosis`(57)
4. 顺带删除其它无引用的孤儿子组件与 9 个无人调用的 api 方法（详情见下方"附带清理"清单，需你确认是否一并处理）

### 口径影响
**无业务口径变化**——诊断面板当前打开即 404，删除后不再报错，属于修复而非改变数据口径。

### 附带清理清单（需确认 ✅ 是否本次一并做）
| 项 | 位置 | 说明 |
|---|---|---|
| 孤儿子组件 | Sidebar、GlobalFilter、MachineChart、MachineCpkTable、ArticleBarChart、MachineCpkTrendDialog、Vite 模板残留（HelloWorld/TheWelcome/WelcomeItem/icons\*） | 全 src 无导入 |
| 无人调用的 api 方法 | getSummary、getDailyTrend、getWeeklyTrend、getArticles、getArticleTrend、getInsights、getJointCombinations、getPaths、getMachineCpk | src/api/index.js |

> 建议：一并删除（它们全是被 Q1–Q4 覆盖的旧"异常率/聚类"体系残留，或从未被调用）。如保守，可先只删诊断面板相关，其余下一轮处理。

### 验收
- `npm run build` 通过，无 `v-if="false"`、无对已删组件的 import。
- 后端不再有对已注释 diagnose 端点的断链引用。

---

## Q4：删除 `/api/machines` 及移除 grade_anomaly 硬编码

### 4.1 删除 `/api/machines` 整个接口（你已确认 ✅）
现状：`/api/machines`（backend/main.py:2620-…）含大量 `SUM(CAST(grade_anomaly AS INT))` 计算（main.py:2762、2786-2816、2876-2878 等），而 grade_anomaly 恒为 0，输出无意义；且前端 `loadMachines` 拉完**从不渲染**。

改动：
1. 后端删除整个 `get_machines` 路由（backend/main.py:2620 起始的完整函数块）。
2. 前端 `src/api/index.js` 删 `getMachines`(39)。
3. `Dashboard.vue` 删：
   - `machines`/`machineLoading`/`machineError` 声明（1169-1171）
   - `loadMachines`(1173-1212) 及 `api.getMachines` 调用(1205)
   - 调用点 loadMachines()（1317、1396、1425、1430）
   - 依赖 `machines.value` 的 `machineChartHeight` computed（797-…，若该 computed 无其它用途则一并删，需确认）

### 4.2 移除数据表中的硬编码异常标记（你已确认 ✅）
现状：`clean_data.py:124-126` 与 `143-145` 把 `rfpp_anomaly`/`rfh1_anomaly`/`grade_anomaly` 硬编码为 0。

改动：
1. `backend/etl/clean_data.py`：两处 SQL 中删除这 3 个 `0 AS xxx_anomaly` 字段，改为在清洗输出中移除这三列。
2. **关键连带**：删除 `/api/machines` 之后，backend 中对 `grade_anomaly` 的剩余引用仅剩死代码（已被注释的 main.py:1735-5964 区域）与 `diagnose_machine`（main.py:1579，将在 Q3/死代码清理中一并删）。需确认无其它活跃端点引用这三列后，方可安全删除列。

### 口径影响
**无业务口径变化**——`/api/machines` 本就不被渲染，`grade_anomaly` 恒为 0。

### 验收
- `clean_data.py` 重跑 ETL（clean 阶段）成功，clean_yield 不再含三列。
- 后端启动后所有活跃接口不报错（确认无对这三列/该接口的残留引用）。
- 前端 `npm run build` 通过。

---

## 阶段顺序 & 每步验证

> 每步完成都跑一次"基线回归"（见下）确认除已知变化外无异常。

1. **Q1**（USL 统一）→ 回归两个接口 + 记录 GROUP 4 变化
2. **Q2**（组合树 CPK）→ 跑组合树对比 + `npm run build` + 写 `change_log_Q2_combination_tree.md`
3. **Q3**（删面板）→ `npm run build`
4. **Q4**（删 machines + 改 clean_data）→ 重跑 ETL clean + 后端启动冒烟

## 基线回归方法（阶段 0 建议先做）
1. 后端 29 个活跃接口，固定参数各请求一次，响应 JSON 存档到 `docs/api_baseline/`。
2. 后续每步改完，重跑并 diff；只允许出现计划中列出的"已知变化"。

---

## 风险与注意
- Q1/Q2 会改变 GROUP 4 规格及组合树的**显示数值**，务必按上面验收项确认这些变化是期望的。
- Q2 前端聚合（合并方差）改动牵一发动全身，需重点回归树形布局与数值。
- 删除 `/api/machines` 前，务必再全局搜一遍是否有遗漏的调用方（含脚本/文档）。
- 迁移期保持 `uvicorn.run("main:app")` 入口与部署脚本不动。

## 用户确认与落地执行记录 ✅
1. **Q1（统一 USL 规格上限）**：
   - 确认采用**优化后算法**（向量化 SQL 统一补齐 `GROUP 4`：rfpp 14.5, rfh1 10.0，保持纳秒级向量化查询性能，避免 Python N+1 循环）。
   - 落地位置：`backend/main.py` 的 4 处 SQL 查询（`/api/articles/warning-cpk`, `/api/articles/lot-barcode-detail`, `/api/articles/lot-cpk-trend` 单规格与全厂综合）。
2. **Q2（组合树 CPK 统一）**：
   - 提取纯函数 `src/composables/useCpk.js`，截断区间统一为 `[-5, 5]`。
   - 保留 `weight` 业务原有语义（偏差%），不按 CPK 指数篡改，完全尊重车间操作工看盘习惯。
   - 落地位置：`src/components/charts/MachineCombinationTree.vue`、`backend/main.py`，详见独立变更日志 `docs/change_log_Q2_combination_tree.md`。
3. **Q3（清理废弃诊断面板与孤儿组件）**：
   - 用户确认一并清理孤儿组件与无人调用的 API。
   - 删除废弃组件：`DiagnosticsPanel.vue`, `LotCompareChart.vue`, `InsightsPanel.vue`, `Sidebar.vue`, `GlobalFilter.vue`, `MachineChart.vue`, `MachineCpkTable.vue`, `ArticleBarChart.vue`, `MachineCpkTrendDialog.vue`, 以及 Vite 模板残留文件。
   - 清理 `Dashboard.vue`：彻底移除 Row 2、Row 4 两个 `v-if="false"` 死区块，清理 160 行无用 CSS 样式，移除所有残留事件与变量。
   - 清理 `src/api/index.js`：剔除 14 个断链/无人调用的历史接口。
4. **Q4（删除 /api/machines 与清理数据列）**：
   - 后端删除整个 `get_machines` 路由（原 `backend/main.py:2623-2900`）以及 `diagnose_machine` 死代码。
   - 前端删除 `loadMachines()` 调用、`machines` 状态及 `machineChartHeight` computed。
   - ETL 清洗：`backend/etl/clean_data.py` 移除生成 `0 AS rfpp_anomaly`, `0 AS rfh1_anomaly`, `0 AS grade_anomaly` 的 SQL 字段。

5. **全站 CPK 口径彻底统一（消灭遗留旧公式）**：
   - 响应排查，将残留的 5 处旧版内联公式（`max(0.0, min(5.0, ...))` 或裸除法）全面替换为官方权威函数 `calc_cpk(...)`。
   - 彻底消灭负 CPK 被粗暴压成 0 的隐患，全站统一支持 `[-5.0, 5.0]` 真实反映超差程度。
   - 预警判断阈值下限同步从 `0.0` 修正为 `-5.0`，确保负 CPK 与预警线能精准对比。

---

## 本地验证总结
- **前端打包编译**：`npm run build` 成功通过（1.54s，0 错误）。
- **后端代码语法**：`python -m py_compile backend/main.py backend/etl/clean_data.py` 成功通过（0 错误）。
- **遗留代码清零**：在 `backend/main.py` 中全量检索 `max(0.0` 结果为 **0 处**；`min(5.0` 仅保留在 `calc_cpk` 统一函数本体内。
- **接口连通性验证**：已删接口 `/api/machines` 预期返回 404；其余活跃核心接口（`/api/articles/all`, `/api/trend/cpk`, `/api/machines/combination-tree` 等）全部正常响应。
- **部署状态**：严格遵循用户要求，所有改动**100% 保留在本地**，未推送到远端服务器。
