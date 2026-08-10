# 看板算法重构与交互升级：变更追踪日志 (Rebuild Change Log)

本日志用于记录重构实施过程中的每一次分模块修改，便于在调试与联调阶段追溯潜在问题。

| 时间 | 模块 | 涉及文件 | 修改描述 | 状态 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-06-29 | 日志初始化 | [rebuild_change_log.md](file:///d:/untitled1/docs/rebuild_change_log.md) | 初始化变更日志，开启分模块追溯 | 🟢 已完成 |
| 2026-06-29 | 后端重构-KMeans | [kmeans_service.py](file:///d:/untitled1/backend/kmeans_service.py) | 实现了 KMeans 肘部法确定最佳 K、正常对照样本聚类分析以及 `get_kmeans_paths` 高性能子集对比服务。 | 🟢 已完成 |
| 2026-06-29 | 后端重构-API | [main.py](file:///d:/untitled1/backend/main.py) | 注册了 `/api/diagnose/paths` 接口；将 `/api/insights` 预警红卡重构为调用 KMeans 服务提取富集机台，消除全局规格单点下钻的污染。 | 🟢 已完成 |
| 2026-06-29 | 前端重构-API与Store | [index.js](file:///d:/untitled1/src/api/index.js), [filter.js](file:///d:/untitled1/src/store/filter.js) | 注册 `getPaths` 接口方法；在 Pinia Store 扩设 `minYieldThreshold` 可变样本过滤值，以及 `selectedMachineName` 等跳转联动状态。 | 🟢 已完成 |
| 2026-06-29 | 前端重构-图表与交互 | [MachineChart.vue](file:///d:/untitled1/src/components/charts/MachineChart.vue) | 绑定 ECharts 点击事件处理器，向父组件抛出 `select-machine` 机台点击事件以支持跨 Tab 穿透跳转。 | 🟢 已完成 |
| 2026-06-29 | 前端重构-总览与根因定位 | [Dashboard.vue](file:///d:/untitled1/src/views/Dashboard.vue) | 左右置换 Tab 1 趋势与横向规格条形图，规格点击仅作本页趋势下钻；在 Tab 2 页头集成局部样本过滤输入，表格机台添加跳转路由。 | 🟢 已完成 |
| 2026-06-29 | 前端重构-深度诊断 | [DiagnosticsPanel.vue](file:///d:/untitled1/src/components/panels/DiagnosticsPanel.vue) | 移去左侧重复表格以防图表压缩；顶部新增下拉选择器，Lot 对照双提升度对称图与诊断病因卡均扩展至 100% 满宽。 | 🟢 已完成 |
