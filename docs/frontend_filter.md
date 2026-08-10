# 🎛️ 过滤器组件文档 (src/components/filters/GlobalFilter.vue)

本组件作为页面顶部的全局控制条，以交互方式修改全局过滤状态，从而联动页面内的各项图表和分析结论。

---

## 1. 界面元素与绑定 (State Bindings)

* **规格型号选择 (`el-select`)**：
  * 双向绑定：`filterStore.selectedArticle`
  * 列表选项：从后端获取的 `articles` 数组，每个选项右侧带小字显示该规格在全表中的总记录数。
* **基准期日期选择 (`el-date-picker`)**：
  * 双向绑定：`filterStore.baselineRange`
  * 类型：`daterange`
  * 占位符：“基准开始” $\rightarrow$ “基准结束”
* **研究期日期选择 (`el-date-picker`)**：
  * 双向绑定：`filterStore.studyRange`
  * 类型：`daterange`
  * 占位符：“研究开始” $\rightarrow$ “研究结束”
* **时间粒度切换 (`el-radio-group`)**：
  * 双向绑定：`filterStore.trendGranularity`
  * 支持类型：`daily`（日度） \| `weekly`（周度）

---

## 2. 核心交互行为 (Interactions)

### 2.1 日期限制与过滤 (`disabledDate`)
为了防止用户选择超出 Parquet 数据集范围的日期，通过 `onMounted` 钩子调用后端 `/api/filters/daterange` 获得数据集的极限起止日期 `date_min` 和 `date_max`，并绑定为限制函数：
```javascript
function disabledDate(t) {
  if (!dateRange.value) return false
  const d = t.toISOString().slice(0, 10)
  return d < dateRange.value.date_min || d > dateRange.value.date_max
}
```

### 2.2 规格联动与重置
* 当规格选择被清除（`val = null`）且当前处于下钻状态时，自动触发 `filterStore.resetDrillDown()` 回退到总览。
* 悬浮控制栏右侧的“刷新”按钮绑定了 `filterStore.reset()`，点击后将一键清空所有已选周期与下钻状态，方便开始全新的根因排查。
