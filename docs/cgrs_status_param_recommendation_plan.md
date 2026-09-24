# 预警规格行动表：机台参数推荐与状态参数对比 —— 执行计划 (Implementation Plan)

> **文档属性**：项目正式实施计划与变更记录 (Implementation Plan & Change Log)  
> **文档路径**：`docs/cgrs_status_param_recommendation_plan.md`  
> **当前状态**：**已按用户最新批注更新**（方案全部收敛至独立单文件 `status_param_recommendation_standalone.py`）  
> **目标**：在看板「核心规格行动表」中点击成型机台「💡 查看推荐参数」时，从原有散碎的调参修改记录片段，全面升级为聚焦 26 项核心成型工艺参数的完整状态底表，双列清晰对比【目前状态值】与【推荐状态值】，对变动项进行高亮标注并在后一列展示【修改变化】（未修改项留空不填）。  
> **架构隔离与代码组织原则**：
> - **单文件先行**：整个方案先全部写在一个独立的 Python 文件 [`backend/status_param_recommendation_standalone.py`](file:///d:/Ava/untitled1/untitled1_v2/backend/status_param_recommendation_standalone.py) 中，**暂不进行接口划分，不写入现有 routers/services 架构**；
> - 待用户在独立脚本中测试确认输出无误后，再行对接与模块拆分。

---

## 0. 现状盘点与改造边界 (Context & Baseline)

### 0.1 核心数据源（直接读取服务器数据文件）
1. **服务器全量历史数据源（主数据源）**：
   - 路径：`\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\CGRS_full_history_data\`
   - 格式：`recipe_full_params_YYYY-MM-DD.parquet`（按日切片的全量参数底表，直接高速读取）；
2. **本地示例源（仅作离线/示例参考）**：
   - 路径：`backend/data/Status-CGRS.csv`（示例样表）。

### 0.2 改造核心诉求（用户最新明确）
1. **不分别读取原始值和改动值，直接读取并展示“结果值”**：
   - **目前状态值（结果值）** = `ParameterValue + TechOffsetValue`；
   - **推荐状态值（结果值）** = `ParameterValue + TechOffsetHistoryValueTo`（若本次修改）或 `目前状态值`（若未修改）；
2. **两列状态值并列展示**：
   - 列 1：【目前状态值】（当前实际运行结果值）
   - 列 2：【推荐状态值】（目标调整后的结果值）
   - 列 3：【修改变化】（有修改项展示变动量，如 `+0.5` / `-0.3`；**未修改项后面留空不填**）
   - 行状态：本次有修改的参数行进行**高亮突出标记**。

---

## 1. 核心业务口径与计算规则 (Business & Math Rules)

### 1.1 聚焦的 26 项核心成型工艺参数清单

| 序号 | 业务参数名称 (Local Name) | 英文标准名称 (Global Name) | ParameterID | 默认单位 | 核心监控工步 |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `IL 安装摩擦` | Lay-on friction IL | 1190003 | % / 常数 | 内衬层 IL 贴合 |
| 2 | `安装高度_IL` | Height | 1190005 | mm | 内衬层 IL 贴合 |
| 3 | `安装高度_PLY1` | Height | 1190068 | mm | 帘布层 PLY1 贴合 |
| 4 | `顶部辊压力 PLY1` | Toproll pressure lay on P1 | 1190075 | bar | 帘布层 PLY1 压辊 |
| 5 | `高度_SW` | Height | 1190212 | mm | 胎侧 SW 贴合 |
| 6 | `左卷边罩位置_胎圈芯定位` | Turn-up ring left position bead setting | 1190259 | mm | 胎圈反包定位 (左) |
| 7 | `右卷边罩位置_胎圈芯定位` | Turn-up ring right position bead setting | 1190260 | mm | 胎圈反包定位 (右) |
| 8 | `卷边终端压力冲击` | Turn-up end pressure shock | 1190261 | bar | 反包成型压力 |
| 9 | `胶囊充气后的卷边罩等待时间` | Turn-up rings delay after bladder inflation | 1190269 | s | 卷边充气时序 |
| 10 | `左侧胶囊高压时间` | Bladder left time high pressure | 1190293 | s | 胶囊高压反包 (左) |
| 11 | `右侧胶囊高压时间` | Bladder right time high pressure | 1190294 | s | 胶囊高压反包 (右) |
| 12 | `安装位置_IL` | Lay-on position | 1190316 | mm | 内衬层 IL 轴向定位 |
| 13 | `安装位置_SSR` | Lay On Position SSR | 1191574 | mm | 缺气保用加强胶 SSR |
| 14 | `安装位置_PLY1` | Lay-on position | 1190318 | mm | 帘布层 PLY1 轴向定位 |
| 15 | `安装位置_PLY2` | Lay-on position | 1190319 | mm | 帘布层 PLY2 轴向定位 |
| 16 | `IL 安装速度` | Lay-on speed IL | 1190338 | m/min | 内衬层贴合速度 |
| 17 | `PLY 1 安装速度` | Lay-on speed PLY 1 | 1190349 | m/min | 帘布层贴合速度 |
| 18 | `PLY 1 安装摩擦` | Lay-on friction PLY 1 | 1190066 | % / 常数 | 帘布层贴合摩擦力 |
| 19 | `SSR 安装摩擦` | Lay-on friction SSR | 1191577 | % / 常数 | 加强胶贴合摩擦力 |
| 20 | `径向位置 PLY 1` | Position radial PLY 1 | 1190073 | mm | 径向贴合深度 |
| 21 | `左侧波纹管式支撑件胎圈芯放置位置` | Bladder unit left bead-setting position | 1190251 | mm | 胎圈撑件定位 (左) |
| 22 | `胎圈芯放置时间` | Bead setting time | 1190272 | s | 胎圈装载时序 |
| 23 | `安装位置_SW` | Lay-on position | 1190323 | mm | 胎侧 SW 轴向定位 |
| 24 | `SW 安装速度` | Lay-on speed SW | 1190392 | m/min | 胎侧贴合速度 |
| 25 | `左侧波纹管式支撑件安装位置` | Bladder unit left lay-on position | 1190395 | mm | 支撑件轴向位置 (左) |
| 26 | `右侧波纹管式支撑件安装位置` | Bladder unit right lay-on position | 1190396 | mm | 支撑件轴向位置 (右) |

---

### 1.2 结果值计算口径（根据用户指示精确对齐）
- **目前状态结果值（Current Actual Value）**：
  $$\text{目前状态值} = \text{ParameterValue} + \text{COALESCE}(\text{TechOffsetValue}, 0.0)$$
- **推荐状态结果值（Recommended Actual Value）**：
  - 若该参数属于本次优质推荐调参事件中的修改项：
    $$\text{推荐状态值} = \text{ParameterValue} + \text{COALESCE}(\text{TechOffsetHistoryValueTo}, 0.0)$$
    $$\text{修改变化} = \text{推荐状态值} - \text{目前状态值}$$
    标记：`is_modified = True`，整行高亮标记；
  - 若该参数未被本次推荐涉及：
    $$\text{推荐状态值} = \text{目前状态值}$$
    $$\text{修改变化} = \text{"" (留空不填)}$$
    标记：`is_modified = False`，正常显示不标记。

---

### 1.3 时间回退三级检索机制 (Fallback Mechanism)
由于状态底表按修改事件存储，看板点击推荐时选定的日期 $T_{\text{target}}$ 不一定当天恰好发生参数修改：
1. **优先匹配当天**：若 $T_{\text{target}}$ 当天存在该机台状态记录，提取当天最后一次生效的参数快照；
2. **回退历史最近日**：若当天该机台无参数记录，自动向上检索在 $T_{\text{target}}$ 之前距离最近的一天的快照；
3. **最早记录兜底**：若历史上无更早记录，取该机台最早的一条记录保底；
4. **输出状态基准日期**：随结果一并返回 `baseline_status_date`。

---

## 2. 实施分步任务清单 (Implementation Tasks Checklist)

### 阶段一：单文件独立实现与自检确认 (当前阶段)

- [ ] **Step 1: 编写独立单文件 `backend/status_param_recommendation_standalone.py`**
  - [ ] 1.1 固化 26 项核心参数的标准配置元数据字典 `CORE_26_BUILDING_PARAMS`；
  - [ ] 1.2 实现直接读取服务器 `\\10.246.97.159\...\CGRS_full_history_data\*.parquet` 的高效加载引擎（带本地 CSV fallback）；
  - [ ] 1.3 实现 `get_machine_status_snapshot(machine, target_date)` 三级时间回退检索逻辑；
  - [ ] 1.4 实现结果值精准计算：`ParameterValue + TechOffsetValue` 与推荐事件 `ParameterValue + TechOffsetHistoryValueTo` 对齐；
  - [ ] 1.5 格式化输出：【参数名称】+【目前状态值】+【推荐状态值】+【修改变化（未修改留空）】+【高亮标记】；
  - [ ] 1.6 编写终端自检测试入口（`if __name__ == '__main__':`），运行并输出典型机台真实数据对比表格。

- [ ] **Step 2: 用户检视与确认**
  - [ ] 2.1 运行独立脚本，输出控制台报表供用户直观核验数值与字段；
  - [ ] 2.2 用户确认计算结果与交互格式符合预期。

---

### 阶段二：后续模块化对接与前端弹窗重构 (待用户确认后执行)

- [ ] **Step 3: 模块划分与路由对接**
  - [ ] 3.1 按照后端重构规范，将单文件能力整合入后端服务；
  - [ ] 3.2 对接 `/api/cgrs/recommended-params` 接口，输出增量对比数据。
- [ ] **Step 4: 前端弹窗重构 (`MachineRecommendParamDialog.vue`)**
  - [ ] 4.1 表格呈现：参数名、目前状态值、推荐状态值、修改变化（变动高亮，未变留空）；
  - [ ] 4.2 变动参数置顶显示，支持实时搜索。

---

## 3. 文件修改总表

| 操作 | 目标文件 | 说明 |
| :---: | :--- | :--- |
| **[NEW]** | `backend/status_param_recommendation_standalone.py` | 独立单文件，自包含所有数据读取、回退匹配与对比计算逻辑 |
| **[PLAN]** | `docs/cgrs_status_param_recommendation_plan.md` | 本执行计划文档 |
