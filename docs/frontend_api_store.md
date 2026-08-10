# 💻 前端 API 请求与全局状态管理文档 (src/api & src/store)

本系统采用 `axios` 作为 HTTP 客户端进行后端交互，并使用 Pinia 作为 Vue 3 全局状态管理引擎，实现跨页面的状态共享（例如时间段设定及下钻目标同步）。

---

## 1. 接口层服务 (src/api/index.js)

`api` 模块对外暴露了以下 API 方法，返回标准的 Axios Promise：

* **基础数据层**：
  * `getSummary()`: 获取全局统计总量。
  * `getDailyTrend(article)` / `getWeeklyTrend(article)`: 获取按天/周聚合的趋势，支持传入特定规格 `article10` 过滤。
  * `getArticleTrend(article)`: 对规格下钻时的特定日度趋势请求。
  * `getFilterArticles()`: 规格下拉列表。
  * `getDateRange()`: 数据集的时间范围极限（用于限制日期选择器的范围）。
* **算法排行层**（参数直接使用结构化对象 `params` 传入）：
  * `getArticles(params)`: 规格排行（支持贡献度、异常数排序，并携带基准期和研究期参数）。
  * `getMachines(params)`: 工位机台熔解排行。
* **深度诊断根因层**：
  * `getInsights(params)`: 获取红/黄/绿自动诊断卡片结论。
  * `getSuspects(params)`: 获取 Step Lift $\ge 1.5$ 的嫌疑机台列表。
  * `getJointCombinations(params)`: 获取高危双机台冲突对。
  * `getLotDiagnosis(params)`: 诊断特定机台下的各批次质量表现。

---

## 2. 全局状态存储 (src/store/filter.js)

`filter` 状态管理仓库定义并维护了全局状态机。

### 2.1 状态声明 (State)
* `selectedArticle` (String | null): 被选中用于单点过滤的规格。
* `dateRange` (Array | null): 全局起止时间限制（[dateMin, dateMax]）。
* `trendGranularity` (String): 趋势图时间粒度 (`daily` | `weekly`)。
* `isDrillDown` (Boolean): 是否处于规格单点下钻的放大细节状态。
* `drillDownTarget` (String | null): 下钻聚焦的规格名称。
* `baselineRange` (Array | null): 用户选择的基准对比期时间段（[baselineFrom, baselineTo]）。
* `studyRange` (Array | null): 用户选择的质量研究期时间段（[studyFrom, studyTo]）。
* `activeTab` (String): 当前高亮标签页 (`overview` | `rootcase` | `diagnose`)。

### 2.2 计算属性 (Getters)
* `hasAnalysisPeriod` (Boolean): 当且仅当 `baselineRange` 和 `studyRange` 均被用户设定完整（长度为2）时，返回 `true`。该值用来控制 Tab 3 "深度诊断" 页面的解锁状态以及各排行图表的排序策略。

### 2.3 状态行为 (Actions)
* `setArticle(article)` / `setDateRange(range)` / `setGranularity(g)`: 基础设定行为。
* `drillDown(article)`: 触发下钻状态，同时将 `selectedArticle` 设为该下钻规格。
* `resetDrillDown()`: 退出下钻模式，并清除所聚焦的规格。
* `setBaselineRange(range)` / `setStudyRange(range)`: 设定基准期与研究期。
* `setActiveTab(tab)`: 更改当前激活标签页。
* `reset()`: 一键重置状态机为出厂默认设置。
