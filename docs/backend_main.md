# ⚙️ 后端服务模块文档 (backend/main.py)

本模块使用 FastAPI 框架构建，内嵌 DuckDB 执行高性能的大数据 Parquet 分析查询，提供轮胎质量分析看板所需的所有计算、筛选与自动诊断功能。

---

## 1. 核心数据模型与配置 (Configurations)

* **数据源**：`yield_flat_table_30d_2_cleaned.parquet` (共 1,486,365 行，36 列)
* **物料映射表 (`LOT_MAP`)**：
  建立前工序物理工位 (`*_workcenter`) 与其使用的原材料/部件批次 (`*_lot`) 的一一对应关系，以便对嫌疑机台进行精确的批次局部/全局对照诊断。

---

## 2. 接口说明 (API Endpoints)

### 2.1 全局摘要与趋势类

#### `/api/summary`
* **功能**：提供检测总量、异常总量、综合异常率及时间范围。
* **数据流转**：从原始 Parquet 聚合计算得到。

#### `/api/trend/daily` 和 `/api/trend/weekly`
* **功能**：返回日度/周度产量与异常率，支持过滤规格 `article10`。
* **防失真逻辑**：日度聚合后，自动丢弃最后一天 (`rows[:-1]`)，以避免因当天排产未收尾导致趋势线末端“非正常下坠”。

---

### 2.2 多排序排行类

#### `/api/articles` (规格排行)
* **交互逻辑**：
  1. 未选时间段时，返回全局排产的 Top 20 规格（以 `anomalies DESC` 排序）。
  2. 已选时间段时，计算研究期较基准期的 Shift-Share 贡献度 `contribution` 并计算绝对值 `abs_contribution`。
  3. 支持根据 `sort_by` (`contribution` 或 `anomalies`) 实时重新对列表排序。

#### `/api/machines` (工位机台排行)
* **逻辑实现**：
  1. 通过 `DESCRIBE` 语句动态抓取列名包含 `workcenter` 但不以 `tu_`/`tb_`/`tg_` 开头的 12 个前工序工艺列。
  2. 运用 `UNION ALL` 在 DuckDB 内部将列纵向融解为 Melted 结构。
  3. 算得各机台在基准期与研究期之间的 Shift-Share 贡献度及在研究期内的 Step Lift。
  4. 支持根据 `sort_by` (`contribution` / `step_lift` / `anomalies`) 返回相应的 Top N 机台。

---

### 2.3 根因自动诊断类

#### `/api/insights` (自动预警结论)
* **核心诊断链**：
  ```
  [获取研究期 Step Lift >= 1.5 且异常数 >= 5 的嫌疑机台]
                          │
         [该工序是否有对应的 lot 原材料批次？]
            ├── 否 ──→ 判定为: 设备系统性工艺漂移
            └── 是 ──→ [拉取该机台下排产量 > 30 且异常数 >= 5 的物料批次]
                            │
                      [计算批次的 Local Lift & Cross-Machine Lift]
                            ├── Local > 1.5 且 Cross > 1.5  ──→ 判定: 机台-批次适配性故障
                            ├── Local > 1.5 且 Cross <= 1.5 ──→ 判定: 全局物料批次缺陷
                            └── 均无超标 ────────────────────→ 判定: 设备系统性工艺漂移
  ```
* **输出**：生成分级 `alerts` 数组（红/黄/绿颜色），直接向前端传递文字化建议。

#### `/api/diagnose/suspects` (嫌疑机台表)
* **功能**：列出 Step Lift $\ge 1.5$ 的嫌疑机台，并显示每台机台的自动诊断原因。

#### `/api/diagnose/combinations` (双机台联合风险)
* **功能**：使用 `itertools.combinations` 在嫌疑机台池中进行跨工序配对，并在 `df` 中计算联合异常率与 Joint Lift。过滤总匹配数小于 50 的小排产组合。

#### `/api/diagnose/lots` (批次诊断明细)
* **功能**：用于下钻诊断特定机台时，以表格方式详细列出该机台加工的各批次、Local Lift、Cross-Machine Lift 及原因判定。
