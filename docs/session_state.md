# 会话状态记录（第二阶段：Q5 后端拆分）

> 更新日期：2026-09-08

## 已完成
- **第一阶段 Q1–Q4 全部完成并通过审查**（详见 `docs/refactor_plan_Q1_Q4.md`）。
- **Q1 复审通过**：旧版内联 `[0,5]` clamp 残留已清零，全站统一走 `calc_cpk`（clamp `[-5,5]`），共 28 处调用；后端 `py_compile` 通过、前端 `npm run build` 通过。
- **Q5 拆分计划已写好**：`docs/plan_Q5_backend_split.md`（core + routers + services 三层，30 接口归属表、`__file__` 稳定化、验收标准、回滚）。**已确认采用推荐三层结构**。尚未开始改代码。

## 正在进行（Q5 执行前需用户拍板 2 件事）

### 1. 死代码 `compute_machine_all_weighted_cpk`（main.py:2537）
- 含义：全文件零调用，确认死代码。
- 建议：**删除**（其功能已被 `/api/machines/cpk/trend` 覆盖）。
- 状态：等用户 yes/no。

### 2. `/api/cgrs/param-recommendation` 的两个"未定义函数"
- `get_param_recommendation`（main.py:6065）调用 `_get_same_section_machines`、`_find_best_event_for_machines`，**全项目无 `def` 定义**（仅调用点 6088-6092）。
- 原因自查：函数被 `try/except` 包住（6111），NameError 被吞掉返回 `{"status":"error","has_recommendation":false}`。
- 现象：接口 HTTP 200、前端页面不崩，但**推荐面板永远是空的**（前端只认 `status:success` 且 `has_recommendation:true`）。
- 用户反馈："这个功能实际在用、应该是可用的" → **疑似服务器运行的是旧版 main.py（函数当时完整），本地这份在重构中丢失了实现**。
- 待办：需用户提供服务器版 `/backend/main.py`，或用 git 历史/旧备份找回这两个函数定义并同步回本地，再进入拆分。**拆分前必须解决，否则拆过去也是坏的**。

## 下一步
1. 用户答复「是否删除 compute_machine_all_weighted_cpk」+「提供 param_recommendation 缺失函数实现/确认服务器版本」。
2. 把两点决定落进 `docs/plan_Q5_backend_split.md` 的待确认项。
3. 开始按计划执行后端拆分（先建包骨架 → core/db.py 稳定 `__file__` → calc/helpers → services → routers → 重写 main.py → 验收）。

## 关键入口/约定（拆分时勿破坏）
- 生产入口：`run_server.py` 里 `uvicorn.run("backend.main:app")`（不可变）。
- 本地入口：main.py 末尾 `uvicorn.run("main:app")`。
- 部署脚本 `deploy_to_server.py`、`scripts/*.bat` 依赖上述入口。
- main.py 末尾挂载 `StaticFiles("/")` 必须保持最后注册。