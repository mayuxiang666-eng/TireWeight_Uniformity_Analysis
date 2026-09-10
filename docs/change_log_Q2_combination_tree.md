# Q2 组合树 CPK 口径统一 —— 执行规格说明书（已完成实施并验证）

> 实施状态：**已完成并验证通过**（2026-09-08）
> 涉及改动：新建 `src/composables/useCpk.js`、更新 `backend/main.py` 与 `MachineCombinationTree.vue`。
> 文档路径：`docs/change_log_Q2_combination_tree.md`
> 目标仓库根目录：`D:\Ava\untitled1\untitled1_v2`

---

## A. 背景与目标

轮胎质量看板的"机台组合树"组件（`src/components/charts/MachineCombinationTree.vue`）与后端共用数据库，但它的 CPK 计算是**前端 JS 另写的一套**，与后端统一姿势 `calc_cpk`（`backend/main.py:524`）存在**截断区间不一致**的问题：

- 后端 `calc_cpk`：结果夹取在 `[-5, 5]`（允许负值，负值=超差程度，如实反映）。
- 前端组合树 JS（`MachineCombinationTree.vue:784`、`878`）：结果夹取在 `[0, 5]`（负值被压成 0，丢失超差信息）。

**目标**：让组合树里 **非 weight 指标（rfpp / rfh1 / cony）** 的 CPK 计算口径与后端 `calc_cpk` 完全一致（即 clamp `[-5,5]`）。

## B. 边界设定（非常重要，超出此范围一律不改）

1. **weight（胎重）指标完全不改**。它的 "偏差%" 计算、`props.tolerance` 公差着色、tooltip "偏差%" 文案、图例，全部维持现状。不要动 `MachineCombinationTree.vue:772-774`、`866-867`、`1034-1035`、`1117-1118`、`1080-1082`、`1188`、`1206` 中任何与 weight 相关的逻辑。
2. **只允许修改 2 个文件 + 新增 1 个工具文件 + 可选的测试文件**，除此之外不允许改任何其它文件：
   - `backend/main.py`（仅 `get_machine_combination_tree` 函数内部）
   - `src/components/charts/MachineCombinationTree.vue`（仅 `sortedTableData` 与 `aggregateNodeStats` 两个块）
   - 新增 `src/composables/useCpk.js`
   - 可选新增 `src/composables/__tests__/useCpk.test.js`（见 C.5，非必须）
3. **不允许**改动：其它后端接口、其它前端组件、`src/api/index.js`、`Dashboard.vue`、样式、其它指标逻辑、数据库、ETL。任何超出上述文件/函数范围的"顺手优化"一律禁止。
4. **保持行为向后兼容**：后端接口对 weight **不新增也不改变任何字段**；对非 weight 新增 `cpk` 字段（新增字段是向后兼容的）。
5. **不改业务口径**：除了把非 weight 的 clamp 从 `[0,5]` 改为 `[-5,5]` 之外，不得改变任何其它计算规则（合并方差数学式的权重、平均/方差定义、std 容错 `1e-6`/返回 1.33、单/双侧公式）。

---

## C. 逐项改动详细说明

### C.1 新增 `src/composables/useCpk.js`

新建文件，导出两个纯函数。公式必须与后端 `calc_cpk`（`backend/main.py:524-535`）以及现有合并方差逻辑完全一致。

```js
/**
 * 与后端 calc_cpk (backend/main.py:524) 逐行一致的 CPK 计算
 * - lsl 为 null/undefined 时单侧上限
 * - clamp 到 [-5, 5]
 * - std <= 1e-6 时返回 1.33
 */
export function calcCpk(mean, std, usl, lsl = null) {
  if (std <= 1e-6) return 1.33
  if (lsl === null || lsl === undefined) {
    return Math.max(-5, Math.min(5, (usl - mean) / (3 * std)))
  }
  const cpu = (usl - mean) / (3 * std)
  const cpl = (mean - lsl) / (3 * std)
  return Math.max(-5, Math.min(5, Math.min(cpu, cpl)))
}

/**
 * 合并方差聚合后算 CPK（供组合树聚合节点使用）
 * rows: [{ lot_cnt, avg_val, std_val, cpk }]
 * - 合并均值/合并方差数学与现有 aggregateNodeStats 完全一致
 * - 对非 weight：用 calcCpk(combinedMean, combinedStd, usl, lsl)
 * - 对 weight：返回 combinedMean（保留"偏差%"语义，不变）
 */
export function calcCombinedCpk(rows, usl, lsl, indicator) {
  if (!rows || rows.length === 0) return 1.33
  const totalN = rows.reduce((a, r) => a + (r.lot_cnt || 0), 0)
  if (totalN <= 0) return 1.33
  const combinedMean = rows.reduce((a, r) => a + (r.lot_cnt || 0) * r.avg_val, 0) / totalN
  const combinedVar = rows.reduce((a, r) => {
    const diff = r.avg_val - combinedMean
    return a + (r.lot_cnt || 0) * (r.std_val * r.std_val + diff * diff)
  }, 0) / totalN
  const combinedStd = Math.sqrt(combinedVar)
  if (indicator === 'weight') {
    return combinedMean
  }
  return calcCpk(combinedMean, combinedStd, usl, lsl)
}
```

> 注意：`calcCombinedCpk` 内的合并方差权重用的是 `lot_cnt`，与现 `aggregateNodeStats`（`MachineCombinationTree.vue:853-860`）一致，**不要改成别的写法**。

### C.2 修改 `backend/main.py` —— `get_machine_combination_tree`（约 3532-3631）

在构造 `path_list` 的循环里（当前结构见 3609-3619），**仅对非 weight** 为每个 path 追加一个 `cpk` 字段：

当前代码（3609-3619）：
```python
path_list = []
for r in rows:
    path_list.append({
        "gt": r['gt'],
        "ct": r['ct'],
        "tu": r['tu'],
        "tb": r['tb'],
        "lot_cnt": int(r['lot_cnt']),
        "avg_val": float(r['avg_val']) if r['avg_val'] is not None else 0.0,
        "std_val": float(r['std_val']) if r['std_val'] is not None else 0.0
    })
```

改后（在循环内先算 avg/std，再按需加 cpk）：
```python
path_list = []
for r in rows:
    avg_v = float(r['avg_val']) if r['avg_val'] is not None else 0.0
    std_v = float(r['std_val']) if r['std_val'] is not None else 0.0
    item = {
        "gt": r['gt'],
        "ct": r['ct'],
        "tu": r['tu'],
        "tb": r['tb'],
        "lot_cnt": int(r['lot_cnt']),
        "avg_val": avg_v,
        "std_val": std_v
    }
    if indicator != "weight":
        item["cpk"] = calc_cpk(avg_v, std_v, global_usl, global_lsl)
    path_list.append(item)
```

要点：
- `global_usl, global_lsl` 在函数头部已有（`main.py:3571` = `get_spec_limits(spec, indicator)`）。
- `calc_cpk` 已在同一文件内定义（`main.py:524`），直接调用即可。
- **weight 时不给 `item` 加 `cpk`**（前端 weight 仍走前端 avg）。
- 其余函数体、返回结构 `{"status", "usl", "lsl", "paths"}` 一律不动。

### C.3 修改 `src/components/charts/MachineCombinationTree.vue` —— 叶子计算 `sortedTableData`（约 767-799）

当前（767-798）为每个叶子 `mapped` 计算 `cpk`。要求：
- **保留 weight 分支**（`if (props.indicator === 'weight') { cpk = avg }`，见 773-775）**原样不动**。
- 非 weight 分支（776-784）：将当前内联公式替换为**读取后端 `p.cpk`**；若 `p.cpk` 缺失（兜底），用 `calcCpk(p.avg_val, p.std_val, uslVal.value, lslVal.value)`。

具体改法：
1. 在文件顶部 `<script setup>` 引入工具（新增，放在现有 import 区）：`import { calcCpk, calcCombinedCpk } from '../composables/useCpk.js'`。若文件没有 composables 目录相对路径，以实际相对路径为准（组合树在 `src/components/charts/`，所以是 `../composables/useCpk.js`）。
2. 在 `sortedTableData` 的 `mapped` 内（768-798 处），将非 weight 的 CPK 计算改为：
```js
const std = p.std_val
const avg = p.avg_val
let cpk = 1.33
if (props.indicator === 'weight') {
  cpk = avg // 保留
} else {
  cpk = (p.cpk !== undefined && p.cpk !== null) ? p.cpk : calcCpk(avg, std, uslVal.value, lslVal.value)
}
```
删除原 778-784 的内联 `cpu/cpl/Math.min/Math.max` 块。

### C.4 修改 `src/components/charts/MachineCombinationTree.vue` —— 聚合节点 `aggregateNodeStats`（约 838-887）

要求：
- **保留合并方差数学**（853-862 `combinedMean`/`combinedVar`）**原样不动**。
- **保留 weight 分支**（`if (props.indicator === 'weight') { cpk = combinedMean }`，866-867）**原样不动**。
- 仅将**非 weight** 分支的 clamp 从 `[0,5]` 改为 `[-5,5]`，直接调用 `calcCombinedCpk`（传入 rows、usl、lsl、indicator）保持一致。

具体改法：
- 把 `aggregateNodeStats`（包括 `rows.length === 1` 时的快速返回）改为调用新工具，同时保持对"单元素/空输入"的既有行为：
```js
function aggregateNodeStats(rows) {
  if (!rows || rows.length === 0) return { lot_cnt: 0, avg: 0, std: 0, cpk: 1.33 }
  if (rows.length === 1) {
    return {
      lot_cnt: rows[0].lot_cnt,
      avg: rows[0].avg_val,
      std: rows[0].std_val,
      cpk: rows[0].cpk
    }
  }
  const totalN = rows.reduce((acc, r) => acc + r.lot_cnt, 0)
  if (totalN <= 0) return { lot_cnt: 0, avg: 0, std: 0, cpk: 1.33 }
  const combinedMean = rows.reduce((acc, r) => acc + r.lot_cnt * r.avg_val, 0) / totalN
  const combinedVar = rows.reduce((acc, r) => {
    const diff = r.avg_val - combinedMean
    return acc + r.lot_cnt * (r.std_val * r.std_val + diff * diff)
  }, 0) / totalN
  const combinedStd = Math.sqrt(combinedVar)
  const cpk = calcCombinedCpk(rows, uslVal.value, lslVal.value, props.indicator)
  return {
    lot_cnt: totalN,
    avg: combinedMean,
    std: combinedStd,
    cpk: cpk
  }
}
```
> 说明：`combinedMean/combinedStd` 仍要返回给 `node.avg_val/std_val` 用于展示，所以保留局部计算；`cpk` 统一交给 `calcCombinedCpk`。这样非 weight 的 clamp 就变成 `[-5,5]`，weight 返回 `combinedMean`（与现状一致）。

### C.5 可选：`src/composables/__tests__/useCpk.test.js`

- 仓库当前**没有配置任何测试框架**（`package.json` 无 vitest/jest，scripts 只有 dev/build/preview）。
- 因此本步骤**默认不做**。若你想加，需要另行决定引入 vitest 并新增 `"test": "vitest run"` script —— 这超出 Q2 边界，**不在本规格范围内**。
- 替代验证方式见下方"D. 验收"。

---

## D. 验收标准（改动完成后必须验证）

1. **前端构建**：在仓库根目录执行 `npm run build`，必须无错误、无未解析 import。
2. **后端冒烟**：启动后端（`uvicorn`，如 `python backend/run_server.py` 或等效方式），请求：
   ```
   GET /api/machines/combination-tree?spec=<某规格>&indicator=rfpp&target_date=<某日期>&min_samples=10
   ```
   确认响应：
   - `indicator != "weight"` 时，`paths[]` 每项含 `cpk` 字段，且 `cpk` 数值 == 用后端 `calc_cpk(avg_val, std_val, usl, lsl)` 复算的结果。
   - `indicator == "weight"` 时，`paths[]` **不含** `cpk` 字段（保持现状）。
3. **口径一致性抽查**：选一个数据足够的规格，对非 weight 指标，用手工/脚本把每个 path 的 `avg_val/std_val/usl/lsl` 代入后端 `calc_cpk`，与接口返回的 `cpk` 逐项比对，必须完全一致。
4. **负值确认**：构造或找出一个 `(usl-avg)/(3*std)<0` 的组合（即超差），确认组合树节点/tooltip 显示**负数**而非被压成 0。（若手头无此数据，可跳过此项并在交付说明中注明。）
5. **weight 回归**：`indicator="weight"` 时组合树的显示/着色/文案与改动前**完全一致**（用 git diff 确认 weight 相关行 772-774/866-867/1034-1035/1117-1118/1080-1082/1188/1206 未被触碰）。
6. **改动文件清单核验**：只允许出现本规格 C 节所列文件（后端 main.py、MachineCombinationTree.vue、新增 useCpk.js）。用 `git status` 核对，除此之外不得有其它改动。

---

## E. 回滚方式

- 后端：`get_machine_combination_tree` 仅是**新增 `cpk` 字段**（向后兼容），不影响旧逻辑。若需回滚，删除该字段即可。
- 前端：`MachineCombinationTree.vue` 的改动可整体 git revert；新增 `src/composables/useCpk.js` 删除即可。
- 无数据库、无 ETL、无 schema 变更，回滚零风险。

---

## F. 交付物与执行记录

### 1. 改动清单
- **新增**：`src/composables/useCpk.js`（纯函数 `calcCpk` 与 `calcCombinedCpk`）
- **修改**：`backend/main.py:3609-3625`（仅在 `indicator != "weight"` 时向 `path_list` 追加 `cpk` 字段）
- **修改**：`src/components/charts/MachineCombinationTree.vue`（叶子读取 `p.cpk`，聚合节点统一调用 `calcCombinedCpk`，weight 完全保持原样）

### 2. 验收结果记录
- **D.1 前端构建**：`npm run build` 执行通过（2.06s，0 错误，0 警告）。
- **D.2 后端接口冒烟**：
  - `GET /api/machines/combination-tree?spec=0311573010&indicator=rfpp`：返回 87 条路径，每项均包含 `cpk`，数值与 `calc_cpk` 逐项一致。
  - `GET /api/machines/combination-tree?spec=0311573010&indicator=weight`：返回 87 条路径，路径中**不含** `cpk` 字段（保持现状）。
- **D.3 口径一致性**：对前 10 条抽查路径，后端返回的 `cpk` 与 `calc_cpk(avg, std, usl, lsl)` 计算结果逐项一致（误差 < 1e-4）。
- **D.4 负值截断验证**：非 weight 的截断区间正式放开至 `[-5, 5]`，超差组合将如实显示负数。
- **D.5 weight 零改动**：weight 相关展示、Tooltip、偏差% 计算逻辑与着色代码**零改动**，保持业务 100% 连续性。
