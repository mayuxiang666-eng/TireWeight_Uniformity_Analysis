# 📋 轮胎质量分析数据源对齐与字段映射指南

本指南针对旧数据源（`yield_flat_table_30d_2_cleaned.parquet`）与清洗好的新数据源（`yield_flat_table_0713cleaned.parquet`）进行深度的字段对齐、数据结构审计和业务逻辑变更评估，以指导后续项目数据源的平滑切换。

---

## 1. 核心变更：数据粒度由“单轮胎”下沉至“组件配方” (Data Grain Shift)

在旧数据源中，数据是按**轮胎只数**（`barcode`）级别表征的：
* **旧数据结构**：每个唯一 `barcode`（轮胎条码）在表里**仅有一行**（共 1,486,365 行，1,486,365 个唯一条码）。
* **新数据结构**：新表中由于引入了 `greentiregutsid`（绿胎胎体组件ID）与 `specissue`（工艺版本号），数据结构粒度下沉。同一个唯一 `barcode` 会对应**多条记录**（共 4,852,036 行，1,160,323 个唯一条码，平均每条轮胎有约 4 条组件记录，部分多达 16 条）。

> [!WARNING]
> **重复行导致的统计偏差风险（Many-to-One Bias）**：
> 审计发现，相同 `barcode` 的所有行中，所有的工序物理机台（`*_workcenter`）、部件批次（`*_lot`）、质量异常标识（`grade_anomaly`）以及检测数值完全相同。唯一的区别是 `greentiregutsid` 和 `specissue`。
> 
> 如果在项目切换数据源时直接使用行级统计，会导致严重的**指标失真**。因为异常胎在组件配方层面的记录数普遍多于正常胎，若不作去重，会导致全局计算的异常率偏高：
> * **去重后（以轮胎只数为分母）**：`grade_anomaly` 异常率为 **`1.0908%`**
> * **去重前（以表行数为分母）**：`grade_anomaly` 异常率为 **`1.1591%`**

---

## 2. 新旧字段对照对齐表 (Field Alignment Map)

新旧数据源字段的增删改对齐明细如下：

| 序号 | 旧字段名 (Old Column) | 新字段名 (New Column) | 旧类型 | 新类型 | 变更状态 | 业务定义与对齐建议 |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| 1 | `barcode` | `barcode` | VARCHAR | VARCHAR | **无变化** | 轮胎唯一条码。新表中存在重复，后续汇总时需去重或聚合。 |
| 2 | `article10` | `article10` | VARCHAR | VARCHAR | **无变化** | 产品 10 位规格代码。 |
| 3 | `grade_anomaly_new` | **`grade_anomaly`** | INTEGER | BIGINT | **重命名/改类型** | 综合质量评级异常标识 (0:正常, 1:异常)。 |
| 4 | `grade_rfppwc_first` | **`rfppwc_first`** | VARCHAR | VARCHAR | **重命名/数值化** | RFPP 首次物理测试值。旧表里为 `'A'` 等字母类别；新表中已清洗为**浮点数字符串**（如 `'76.59084800'`），如需数值计算需显式转换。 |
| 5 | `grade_rfh1wc_first` | **`rfh1wc_first`** | VARCHAR | VARCHAR | **重命名/数值化** | RFH1 首次物理测试值。旧表里为 `'A'` 等字母类别；新表中已清洗为**浮点数字符串**（如 `'50.79632800'`）。 |
| 6 | - | **`greentiregutsid`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 绿胎胎体组件ID。此字段引入是数据膨胀的根源。 |
| 7 | - | **`specissue`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 工艺/规格版本 issue。主要分布为 `'001'` 到 `'010'`。 |
| 8 | - | **`group`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 分群标签，如 `'GROUP 1'`, `'GROUP 2A'`, `'GROUP 2B'`, `'GROUP 3'`。 |
| 9 | - | **`rfpp_anomaly`** | - | BIGINT | <font color="green">**[NEW]**</font> | RFPP 检测项异常标识 (0:正常, 1:异常)。 |
| 10 | - | **`rfh1_anomaly`** | - | BIGINT | <font color="green">**[NEW]**</font> | RFH1 检测项异常标识 (0:正常, 1:异常)。 |
| 11 | - | **`anomaly_code`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 首位主缺陷异常代码，如 `'02BD'`, `'90MX'`。 |
| 12 | - | **`anomaly_code_1`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 辅助缺陷异常代码 1。 |
| 13 | - | **`anomaly_code_2`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 辅助缺陷异常代码 2。 |
| 14 | - | **`anomaly_code_3`** | - | VARCHAR | <font color="green">**[NEW]**</font> | 辅助缺陷异常代码 3。 |
| 15 | - | **`tb_last_workcenter`** | - | VARCHAR | <font color="green">**[NEW]**</font> | TB 检测工序最后一次加工设备。 |
| 16 | - | **`tg_last_workcenter`** | - | VARCHAR | <font color="green">**[NEW]**</font> | TG 检测工序最后一次加工设备。 |
| 17 | - | **`tu_last_workcenter`** | - | VARCHAR | <font color="green">**[NEW]**</font> | TU 检测工序最后一次加工设备。 |
| 18 | `grade_cony_first` | - | VARCHAR | - | <font color="red">**[DELETE]**</font> | 已废弃。 |
| 19 | `grade_lfh1wc_first` | - | VARCHAR | - | <font color="red">**[DELETE]**</font> | 已废弃。 |
| 20 | `grade_lfppwc_first` | - | VARCHAR | - | <font color="red">**[DELETE]**</font> | 已废弃。 |
| 21 | `grade_plys_first` | - | VARCHAR | - | <font color="red">**[DELETE]**</font> | 已废弃。 |
| 22 | `grade_rfh2wc_first` | - | VARCHAR | - | <font color="red">**[DELETE]**</font> | 已废弃。 |
| 23 | `tu_grade_first` | - | VARCHAR | - | <font color="red">**[DELETE]**</font> | 已废弃。 |
| 24~48 | *其他工序/物料字段* | *保持一致* | VARCHAR | VARCHAR | **无变化** | 包含 12 个前工序机台（`ccs_workcenter`、`gt_workcenter`等）以及对应的部件批次（`bead_lot`、`tread_lot`等）。旧表中的 `tb_first_workcenter`, `tg_first_workcenter`, `tu_first_workcenter` 依然在新表中完整保留。 |

---

## 3. 核心变更细节审计分析 (Audit Insights)

### 3.1 字段重命名影响
1. **主质量指标重命名**：
   - 旧代码中频繁使用 `grade_anomaly_new` 进行异常数统计和比率计算。
   - 对齐建议：后端所有 API SQL 查询中（如 `main.py`），需要将 `grade_anomaly_new` 全量替换为新字段 `grade_anomaly`。
2. **测试数据重命名与类型变更**：
   - 字段 `grade_rfppwc_first` 和 `grade_rfh1wc_first` 重命名为 `rfppwc_first` 和 `rfh1wc_first`。
   - 旧数据中其数值是分类文本（如 `'A'`），而新数据中是类似 `'76.59084800'` 的物理量化数值。这为以后直接计算物理偏差提供了数据支持。

### 3.2 引入 `greentiregutsid` 导致的行膨胀
对新数据源进行去重检测：
* 总行数：**4,852,036**
* 完全重复行（42列全部相同）：**12,983 行**
* 剔除完全重复行后的唯一粒度：**`(barcode, greentiregutsid, specissue)`**
* 在一个 `barcode` 包含的多行记录中，除了这二者，其他属性均完全一致。这意味着数据扩展只发生在这两个组件维度上，不影响其他基础机台和批次信息的关联。

---

## 4. 后续对切换实现方案的修改建议

为保证看板在切换数据源后计算逻辑的准确度，建议在后端 `backend/main.py` 的 DuckDB 加载阶段做如下对齐处理：

### 方案 A：在内存表中提前去重（推荐，改动极小）
如果在看板层面不需要下钻到“绿胎组件 ID (`greentiregutsid`)”和“配方版本 (`specissue`)”的细粒度统计，可以在载入内存表时直接执行 `DISTINCT ON` 或者是 `MAX()` 聚合，将数据粒度还原为**每条轮胎唯一行**：

```python
# 修改 main.py 中的加载逻辑
db_conn = duckdb.connect()
db_conn.execute(f"""
    CREATE OR REPLACE TABLE clean_yield AS 
    SELECT 
        barcode,
        ANY_VALUE(article10) AS article10,
        ANY_VALUE(grade_anomaly) AS grade_anomaly, -- 旧 grade_anomaly_new
        ANY_VALUE(rfppwc_first) AS rfppwc_first,
        ANY_VALUE(rfh1wc_first) AS rfh1wc_first,
        ANY_VALUE(rfpp_anomaly) AS rfpp_anomaly,
        ANY_VALUE(rfh1_anomaly) AS rfh1_anomaly,
        ANY_VALUE(anomaly_code) AS anomaly_code,
        ANY_VALUE(anomaly_code_1) AS anomaly_code_1,
        ANY_VALUE(anomaly_code_2) AS anomaly_code_2,
        ANY_VALUE(anomaly_code_3) AS anomaly_code_3,
        ANY_VALUE(group) AS "group",
        -- 保留原本所有的物理工位与批次列
        ANY_VALUE(ccs_workcenter) AS ccs_workcenter,
        ANY_VALUE(gt_workcenter) AS gt_workcenter,
        ANY_VALUE(ct_workcenter) AS ct_workcenter,
        ANY_VALUE(ct_shiftdate) AS ct_shiftdate,
        ANY_VALUE(bead_lot) AS bead_lot,
        ANY_VALUE(bead_workcenter) AS bead_workcenter,
        ANY_VALUE(tread_lot) AS tread_lot,
        ANY_VALUE(tread_workcenter) AS tread_workcenter,
        ANY_VALUE(inner_liner_lot) AS inner_liner_lot,
        ANY_VALUE(inner_liner_workcenter) AS inner_liner_workcenter,
        ANY_VALUE(sidewall_lot) AS sidewall_lot,
        ANY_VALUE(sidewall_workcenter) AS sidewall_workcenter,
        ANY_VALUE(first_breaker_lot) AS first_breaker_lot,
        ANY_VALUE(first_breaker_workcenter) AS first_breaker_workcenter,
        ANY_VALUE(second_breaker_lot) AS second_breaker_lot,
        ANY_VALUE(second_breaker_workcenter) AS second_breaker_workcenter,
        ANY_VALUE(first_ply_lot) AS first_ply_lot,
        ANY_VALUE(first_ply_workcenter) AS first_ply_workcenter,
        ANY_VALUE(wound_cap_ply1_lot) AS wound_cap_ply1_lot,
        ANY_VALUE(wound_cap_ply1_workcenter) AS wound_cap_ply1_workcenter,
        ANY_VALUE(wound_cap_ply2_lot) AS wound_cap_ply2_lot,
        ANY_VALUE(wound_cap_ply2_workcenter) AS wound_cap_ply2_workcenter,
        ANY_VALUE(tb_first_workcenter) AS tb_first_workcenter,
        ANY_VALUE(tb_last_workcenter) AS tb_last_workcenter,
        ANY_VALUE(tg_first_workcenter) AS tg_first_workcenter,
        ANY_VALUE(tg_last_workcenter) AS tg_last_workcenter,
        ANY_VALUE(tu_first_workcenter) AS tu_first_workcenter,
        ANY_VALUE(tu_last_workcenter) AS tu_last_workcenter
    FROM read_parquet('{DATA_PATH}')
    GROUP BY barcode
""")
```
*这样可以完全避免修改后端后续几千行的 SQL 查询语句，所有针对 `grade_anomaly`（重命名后）的 `COUNT(*)` 和 `AVG()` 都能保持统计学的无偏性。*

---

## 5. 待与您确认的业务逻辑疑问 (Open Questions)

在进行项目代码修改前，有以下几点需要和您核对以保证改动符合预期：

1. **是否需要引入新的分析维度？**
   - 新增了 `anomaly_code`（缺陷代码）、`group`（分群）、以及分项异常标识 `rfpp_anomaly` 与 `rfh1_anomaly`。后续看板是否需要新增对应的过滤项、分类统计卡片或分析图表？
2. **`rfppwc_first` / `rfh1wc_first` 的数值分析需求**：
   - 之前这两个字段是类别文本 `'A'`，目前是浮点数值。看板是否需要对其展示平均值、偏差分布趋势，还是仅用于在列表中呈现？
3. **已删除的废弃字段确认**：
   - 字段 `grade_cony_first`、`grade_lfh1wc_first` 等已被删除。目前后端代码并未显式调用它们，但请问您的前端页面或导出的数据报表中，是否有逻辑依赖这些字段？
4. **TB/TG/TU 终端检测工序的新增字段 `_last_workcenter`**：
   - 新增了 `tb_last_workcenter`、`tg_last_workcenter`、`tu_last_workcenter`。根据原看板的筛选逻辑，检测端工序是不参与“前工序机台聚类与根因诊断”的。请问这三个新增的检测端字段是否需要特殊处理，还是继续保持被过滤的状态？
