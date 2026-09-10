# 项目全局记忆与上下文压缩总结 (PROJECT_MEMORY)

> **全局记忆管理规则**：
> 每当输入 `压缩上下文`、`任务总结`、`开启新任务` 或 `开始新功能` 时，Agent 将自动把当前的架构决策、开发进度、核心模块变更与关键结论进行压缩总结，覆盖更新写入本文件。

---

## 1. 项目整体背景与技术栈

- **系统名称**：轮胎质量与均匀性分析看板 (Tire Weight & Uniformity Analysis)
- **技术栈**：
  - 前端：Vite + Vue 3 (Composition API / Setup) + Element Plus + ECharts 5
  - 后端：Python FastAPI + DuckDB 内存分析引擎 + Pandas
- **主要工作区路径**：[untitled1_v2](file:///d:/Ava/untitled1/untitled1_v2)
- **服务器部署共享路径**：`\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis`

---

## 2. 核心功能模块与设计约定

### CGRS 调参前后全工序路径拆分与趋势对照 (CgrsRecordDialog.vue)
- **分析逻辑**：按成型 GT ➔ 硫化 CT ➔ 终检 TU 拆分全工序路径，针对调参事件提取改前/改后各工步的数据表现。
- **CGRS 路径筛选与对比计算重构规则**：
  - **样本抓取与跨天上限**：单个路径改前/改后最多抓取 **20 胎**，受调参时间戳分隔；在界限内允许跨天（最多 1 天）。
  - **双侧最低样本约束**：单条路径改前与改后必须同时满足 **$N_{\text{before}} \ge 5$ 且 $N_{\text{after}} \ge 5$**。
  - **2.5 倍样本失衡整条过滤**：比例 $R = \frac{\max(N_{\text{before}}, N_{\text{after}})}{\min(N_{\text{before}}, N_{\text{after}})} > 2.5$ 时，**直接整条路径剔除**。
  - **无有效对比路径事件置灰**：若拆分路径均被剔除，`[第 X 次]` 切换按钮在 CGRS 弹窗中**置灰禁用 (`disabled`)**。

---

## 3. 重磅更新记录 (2026-08-27)

### 1. 产量平方根平滑机台贡献度算法 (Square-Root Volume Smoothing)
- **解决核心痛点**：
  - 旧算法采用**线性产量占比 ($\text{Volume} = N / N_{\text{total}}$)**，导致 98% 巨额权重的独占开满机台（如 `TU8`）“替人背第一大锅”，而局部 CPK 崩塌至 0.31 的真元凶（如 `CU621`，50 胎）因仅占 9.6% 产量被线性压缩至 `-0.011` 而惨遭掩盖。
- **数学公式升级**：
  $$\text{Impact Score} = \text{Contribution (净负面偏离度)} \times \frac{\sqrt{\text{machTires}_m}}{\sum_i \sqrt{\text{machTires}_i}}$$
- **实测成效**：
  - 1300 胎 vs 50 胎的 26 倍巨额产量差距被平滑缩小至 **5.1 倍**；
  - `CU621` 影响分跃升至 `-0.038 / -0.031`（全厂绝对值最大），**系统自动登顶 Rank 1 (Critical) 并在全系统标记红光发光预警**；
  - `TU8` 影响分降至 `-0.025`，降为 Rank 2 负贡献机台，不再误判为第一大元凶。

### 2. 全系统 100% 联动同步范围
- **后端服务 (`backend/main.py`)**：
  - 核心评估函数 `get_top_warning_machines()`：全线采用 `Impact Score = Contrib * sqrtVolumeShare`；
  - API `/api/machines/process-sankey` & `/api/machines/critical-machine`：同步输出最新瓶颈设备。
- **前端组件联动**：
  - `MachineCombinationTree.vue` (机台组合树图)：顶栏 Panel、Tree Node 发光规则全面联动 `CU621`；
  - `MachineProcessSankeyChart.vue` (单日桑基图)：顶部警示栏、Help 浮窗、桑基图红色发光节点同步高亮 `CU621`；
  - `MachineCpkTrendDialog.vue` (CPK双线趋势图)：同规格 CGRS 调参 Pins 与双重差分相对劣化预警正常工作。

---

---

## 5. 重磅更新记录 (2026-09-04) - 核心规格行动表重构与负向区域合并

### 1. 功能区域深度整合
- **负向规格升级为核心规格行动表**：彻底替换原有条形柱状图，升级为 [CoreSpecActionTable.vue](file:///d:/Ava/untitled1/untitled1_v2/src/components/tables/CoreSpecActionTable.vue)；
- **面板比例扩增**：左侧面板扩增至 40%（右侧 60%），超出支持平滑横向滚动条；
- **解耦树状图触发**：从 [MachineCombinationTree.vue](file:///d:/Ava/untitled1/untitled1_v2/src/components/charts/MachineCombinationTree.vue) 中彻底移除原机台诊断弹窗点击事件。

### 2. 严格两级智能排序规则
1. **第一层级（预警颜色）**：🔴 红色预警（调参恶化 / 持续霸榜）严格置顶 ➔ 依次是 🟠 橙色预警（降幅超 35% / 持续在榜） ➔ 🟡 黄色预警 ➔ ⚪ 无预警；
2. **第二层级（负向拉低严重度）**：同预警颜色内，严格按负向贡献度绝对值由大到小（最严重到较轻）降序排列。

### 3. 字段与交互表现
- **预警规格**：单元格**仅展示纯规格编号**（如 `0359728000`）；期别标签（三期/四期）、负向贡献度得分、单规格 CPK / 偏差率、全厂基准、单日产量、主要责任机台全部集中在鼠标悬浮 Tooltip 卡片中展示；
- **预警机台**：状态指示球（🔴/🟠/🟡）+ 机台代号，悬浮展示详细恶化原因；
- **CPK 变化率**：展示对比前 3 天均值变化率（红/绿胶囊）；
- **行动措施**：GT/CT 机台展示「💡 查看推荐参数」按钮（严格校验过去 30 天是否有调参推荐，有则展示高亮蓝标，无则显示 `-` 避免空弹窗），TU 展示标杆推荐机台；
- **规格间区域视觉区分**：每个规格使用微立体胶囊徽标展示编号，各规格之间采用明显的加深实线分隔底线（`2px solid #94a3b8`）与斑马交替底色（白底与柔和浅灰交替），使不同规格之间的区域边界一目了然；
- **固定高度与垂直滚动**：左侧卡片锁定与右侧一致的 650px 固定高度，表格内部启用垂直平滑滚动条（`overflow-y: auto`），表头保持固定置顶（Sticky Header），彻底消除表格过长撑开页面的问题；
- **下钻联动**：点击任意规格行联动全屏，表头提供「查看全量」与「单规格折线图」入口。

### 4. 规格排列计算核心公式与优先级
- **规格排序计算逻辑**：
  $$\text{CPK 负向贡献得分 (Stable Score)} = (\text{全厂加权综合均值 CPK} - \text{该规格单日单值 CPK}) \times \text{该规格单日排产条数 } N$$
  （注：单规格 CPK 越低、产量越大，拉低全厂综合质量的负向贡献绝对值越大）
- **两级排序策略**：
  1. **第一优先级（预警颜色梯队）**：🔴 红色规格（调参恶化 / 连续2天以上霸榜#1）置顶 ➔ 🟠 橙色规格（跌幅超35% / 连续3天在榜） ➔ 🟡 黄色规格（普通负贡献在榜）；
  2. **第二优先级（负向贡献度绝对值）**：在相同预警颜色梯队内部，严格按照上述公式算出的负向拉低贡献度绝对值从大到小降序排列。
  3. **第三优先级（规格内机台排序）**：规格合并单元格内部多机台，严格按 🔴 > 🟠 > 🟡 顺序排列。

### 4. 后端性能飞跃
- [main.py](file:///d:/Ava/untitled1/untitled1_v2/backend/main.py) 中的 `get_articles_warning_cpk` 接口优化为 Top 规格多线程并发诊断 (`ThreadPoolExecutor`)，响应耗时由 30+ 秒降至 0.84 秒。

### 2. 诊断状态标签【红 / 橙 / 黄】三级颜色分级体系与判定流向 (2026-09-07 标准化持久化)

#### 1. 完整判定流向与前置条件 (严格执行以下漏斗顺序)
1. **阶段 1：嫌疑机台初筛（Top 3 负向拉低设备）**：
   - 调用 `get_top_warning_machines(n=3, ...)`；
   - 算法公式：$$\text{Impact Score} = \text{Contribution (净负偏离度)} \times \frac{\sqrt{\text{machTires}}}{\sum \sqrt{\text{machTires}}}$$
   - 采用产量平方根平滑占比，缩小极端产量机台与中小机台的权重差距，选出对该规格拉低最严重的至多 3 台设备（GT成型、CT硫化、TU终检）。
2. **阶段 2：前置恶化硬过滤（守门门槛，非恶化机台绝不上榜）**：
   - 提取该机台目标日 $T_0$ 的单班 CPK，与该机台在该规格前 3 天历史均值 $\mu_{3d}$；
   - 相对变化率：$\text{cpk\_pct\_change} = \frac{T_0 - \mu_{3d}}{\mu_{3d}} \times 100\%$；
   - **硬过滤原则**：`if cpk_pct_change is not None and cpk_pct_change > 0: continue`（当班整体质量相比历史处于改善通道的机台，坚决不进入负向恶化监控榜）。
     - *业务确认准则（2026-09-07 确认）*：即使机台在桑基图中因绝对负偏离度高或有调参记录而高亮，只要当班 CPK 较前 3 天均值有正向改善（$\text{cpk\_pct\_change} > 0$），严格视为处于改善/回升通道，予以硬过滤排除，不在左侧核心行动表中生成警示行动（如 2026-09-04 的 TB254 前 3 天均值 0.735，今日 0.789，变化率 +7.4% > 0，严格不予预警）。
3. **阶段 3：多日持续度统计**：
   - 回溯前 1 天与前 2 天负贡献榜单，统计 `days_on_board`（近 3 天在榜天数）与 `days_rank1`（近 3 天霸榜 #1 天数）。
4. **阶段 4：CGRS 调参因果分析（仅 GT / CT，废除虚拟占位表 cgrs_events，复用统一计算引擎）**：
   - 调用成熟因果对比函数 `calculate_cgrs_cpk_comparison`：
     - 圈定观察日终检测量样本的实际加工时间跨度 $[T_{\min}, T_{\max}]$；
     - 提取调参时刻改前 20 胎 vs 改后 20 胎，按全工序控制变量路径拆分并计算有效加总 $\Delta CPK$；
     - **恶化判定**：有效调参事件中存在 $\Delta CPK < 0$ 时，准确标记 `has_degraded_tuning = True`（如 TB285 在 08-29 调参后 $\Delta CPK = -0.736, -36.5\%$）。

#### 2. 三级预警判定瀑布流
- **🔴 红色（最高危险度 / 立即干预）**：
  - **前置条件**：满足以下任一条件即可命中：
    1. `🔴 调参恶化 (查看推荐)`：`has_degraded_tuning == True`（检测到 CGRS 调参且有效加总 $\Delta CPK < 0$）；
    2. `🔴 持续霸榜(#1)`：`days_rank1 >= 2`（该机台在近 3 天中有 $\ge 2$ 天位列全厂负贡献榜第 1 名）。
  - **视觉表现**：红色状态球 🔴，规格内部第一优先级绝对置顶。
- **🟠 橙色（中度警示 / 降幅超 35% 或 持续在榜#2-#3）**：
  - **前置条件**：**非红色**前提下，满足以下任一条件：
    1. `🟠 骤降超35%`：当班 CPK 相比前 3 天均值跌幅超过 35%（$\text{cpk\_pct\_change} \le -35\%$）；
    2. `🟠 持续在榜`：近 3 天均进入负贡献榜但非霸榜 #1（`days_on_board >= 3 且 days_rank1 < 2`）。
  - **视觉表现**：橙色状态球 🟠。
- **🟡 黄色（普通提示 / 监控关注）**：
  - **前置条件**：**非红、非橙**的兜底情况：
    - `🟡 新上线`：该机台在观察日前 3 天无生产记录，今日新换型上线排产，处于试产磨合阶段；
    - `🟡 持续在榜`：近 3 天有 2 天进入负贡献监控榜；
    - `🟡 负贡献在榜`：当日单机 CPK 偏低，位列拉低监控榜。
  - **视觉表现**：黄色状态球 🟡。
  - **新上线专属徽标**：在「CPK 变化率」列中，新上线机台不再显示生硬的 `-`，而是渲染为专属优雅徽标 **`新上线`**（`.pct-new`），悬浮展示说明卡片：“该机台前 3 天未生产该规格，今日新换型上线排产，处于试产磨合阶段，暂无历史对比基准”。

#### 3. 规格机台双层智能排序体系
- **第一层（规格内机台排序）**：🔴 红色机台置顶 ➔ 🟠 橙色 ➔ 🟡 黄色；同预警颜色内，严格按**负向贡献度严重度排名优先 (`Rank 1 > Rank 2 > Rank 3`)**，跌幅仅作为三级平局决胜键。
- **第二层（全厂规格排序）**：规格预警颜色取其内部机台最高级别（🔴 > 🟠 > 🟡）；在相同预警颜色梯队内，严格按照公式算出的负向拉低贡献得分绝对值 $|StableScore|$ 降序排列。
- **前端小球质感与色彩规范**：
  - `.status-ball` 移除外圈光晕边框（`box-shadow: none`、`border: none`）；
  - **🔴 红色小球**：采用沉稳肃穆的**暗红/深绯红渐变**（`#b91c1c` ➔ `#881337` ➔ `#4c0519`），突出最高危险度与严肃性；
  - **🟠 橙色小球**：采用**高饱和度的明亮暖日橙渐变**（`#ffa600` ➔ `#ff6600` ➔ `#d84315`，饱和度拉满），与暗红形成鲜明的亮暗与色相双重反差，一目了然！
  - **🟡 黄色小球**：采用**清透明亮的柠檬金黄渐变**（`#fef08a` ➔ `#eab308` ➔ `#a16207`）。

### 3. 工段差分化【行动建议】(2026-09-04 最新升级)
1. **参数推荐行动统一文案**：凡是针对成型 (GT/TB) 或硫化 (CT/CU) 的工艺参数推荐，按钮文案统一命名为 **`💡 查看推荐参数`**（深蓝高亮按钮，点击可弹出参数修改轨迹与推荐详情；若无有效参数则显示 `-` 不显示按钮）。
2. **终检 (TU) 机台行动建议**：不再展示原有的 `🔍 检查该机台`，而是**直接推荐历史最佳 CPK 机台**，**复用该规格在全量最佳生产路径中的最好机台结果**（展示为绿色高亮标签 **`💡 推荐机台: ${bestTuMachine}`**，例如 `💡 推荐机台: TU19`），悬浮 Tooltip 详细展示该标杆 TU 机台在全量历史数据集中的 CPK 均值表现与调配指引。

### 4. 历史最佳工艺参数因果推荐与修改轨迹重构 (MachineRecommendParamDialog.vue & main.py)
- **严格回溯基准日原则（彻底杜绝未来数据穿越）**：
  - 接口强制接收并校验观察基准日 `target_date`（如 `2026-08-17`），检索范围强制锁定为 `[target_date - 30天, target_date]`；
  - 坚决杜绝数据库最新时间（如 9月3日）对历史观察日的数据泄漏；
- **真因果质量择优（CPK 改善判定）**：
  - 对 30 天窗口内调参事件，提取调参前后 50 条生产样本，计算 $\Delta CPK = CPK_{\text{after}} - CPK_{\text{before}}$；
  - 严格优先推荐带来质量显著改善（$\Delta CPK > 0$）、改后 CPK 处于高位的调参事件；
- **成型机 (GT) 与硫化机 (CT) 工艺参数推荐与行动建议显示规则 (2026-09-04 最新更新)**：
  1. **严格工段物理隔离（绝不跨工段）**：
     - 成型机 (GT/TB) 仅检索 `Workcenter LIKE 'TB%' OR Workcenter LIKE 'GT%'`，与 `gt_workcenter` 生产数据因果挂钩，绝不混入硫化参数；
     - 硫化机 (CT/CU) 仅检索 `Workcenter LIKE 'CU%' OR Workcenter LIKE 'CT%'`，与 `ct_workcenter` 生产数据因果挂钩，绝不混入成型参数。
  2. **成型机 (GT) 推荐检索顺序（彻底删除前 5 位模糊匹配）**：
     - 成型机参数与规格严格绑定，仅匹配 10 位全规格或前 7 位规格（`ProdSpecific2 = article10 OR ProdSpecific2 LIKE 'spec7%'`）；
     - **完全删除前 5 位模糊匹配**：若本机台及同工段其他成型机在过去 30 天均无该规格调参记录，则直接返回无推荐参数，不在前端显示行动建议；
     - **优先级 1（同规格同机台）**：优先推荐本机台在该规格近 30 天内的最佳调参；
     - **优先级 2（同工段同规格其他机台）**：若本机台无调参，推荐在实际生产过该规格的同工段机台中该规格的最佳调参。
  3. **硫化机 (CT) 推荐检索顺序（参数不绑规格，追溯固定机台生产表现）**：
     - **硫化机调参不绑定规格**：在 `cgrs_records` 中不加规格过滤条件；
     - **固定机台生产追溯**：每个规格生产的硫化机基本固定，系统从 `clean_yield` 中自动提取历史上生产该规格的固定硫化机列表；
     - **追溯各日期表现**：追溯发生参数修改后，该机台生产目标规格的实际 CPK 表现（$\Delta CPK$ 与调参后 CPK）；
     - **优先级 1（本机台在该规格上的表现）**：优先推荐本机台调参后在该规格上带来 CPK 显著改善或表现优秀的参数；
     - **优先级 2（其他固定硫化机中的最佳参数）**：若本机台无调参或表现不佳，推荐生产该规格的其他固定硫化机（如 `CUL02`、`CUK21`）在调参后 CPK 最佳的参数版本。
  4. **无参数时不显示行动按钮**：
     - 若机台无有效工艺调参推荐（`has_recommendation == false` 或 `params.length === 0`），“行动建议”列**不显示行动按钮**（显示 `-`），杜绝误导用户；
     - 仅当切实存在推荐参数时，才展示 `💡 推荐成型/硫化工艺参数` 按钮供用户点击查看参数修改轨迹与效果。

---

## 5. 当前系统状态与验证

- **前后端运行状态**：
  - 后端 FastAPI 服务（端口 8000）：已重新加载运行最新逻辑，端口 8000 监听正常。
  - 前端 Vite 服务（端口 5173）：正常运行，`npm run build` 生产构建成功通过。
- **关键问题修复与实测结论 (2026-09-04 核心规格行动表修复)**：
  1. **机台排序修正（负向贡献度排名优先）**：
     - **修复前原因**：规格内同预警颜色机台原按降幅 `cpk_pct_change` 排序，导致跌幅 -44.9% 的 TU5 排在第一，而负向贡献度绝对值最大（Rank 1）的硫化机 `CUE01`（跌幅 -20.0%）被排在第三。
     - **修复后规则**：同颜色预警等级内，严格按照**负向贡献度严重度排名优先 (`Rank 1 > Rank 2 > Rank 3`)**，跌幅仅作为三级平局决胜键；
     - **实测生效**：规格 `0314813043` 列表现已变为：① `🟠 CUE01`（Rank 1 硫化机，负贡献 -0.0345）➔ ② `🟠 TU7`（Rank 2）➔ ③ `🟠 TU5`（Rank 3），完全与右侧桑基图红色发光第一责任节点对齐！
  2. **规格间区域视觉区分增强与小球列严格对齐**：
     - **小球严格基准列对齐**：重构预警机台单元格布局（固定 90px 居中容器 + 左对齐 10px 高质感 CSS 渐变微光小球），彻底消除不同字符长度导致的左右抖动（zigzag），使整列小球与机台名称在垂直方向上 100% 呈一条直线对齐；
     - **全表降低颜色饱和度 (Design-MD)**：
       - 行动措施由高饱和纯蓝/高亮纯绿重构为现代低饱和清爽胶囊（`#eff6ff` 淡蓝底配深蓝字、`#f0fdf4` 鼠尾草淡绿底配深绿字）；
       - CPK 跌幅由刺眼厚重红底重构为优雅浅玫瑰粉雾胶囊（`#fef2f2` 底色配 `#dc2626` 文字）；
       - 顶部预警规则由高亮黄底重构为极简低饱和素雅灰蓝卡片（`#f8fafc` 配 `#e2e8f0` 边框）；
       - 规格组交替底色与分隔线降低对比冲击，呈现专业顶级看板质感。
  3. **表格 50% 宽度拓宽、无边框纯净排版、字体放大 20% 与去图标优化 (2026-09-04)**：
     - **面板比例 50% / 50%**：左侧核心规格行动表扩宽至 50%（`flex: 5`），右侧工序流转占 50%（`flex: 5`），列宽充裕，彻底避免水平拥挤；
     - **预警规格去外边框重构**：彻底移除规格代码的外边框、背景阴影胶囊，采用现代纯净排版，悬浮优雅变色；
     - **全表字体放大 20%**：表头升至 14.5px，规格代码升至 15.5px，机台代码升至 15px，CPK 变化率升至 14.5px，行动措施升至 13.5px，大幅提升工业场景看板可读性；
     - **彻底去除图标**：去除行动按钮中的 `💡` 等符号，呈现纯文字洁净视觉（`查看推荐参数`、`推荐机台: TU13`）。
  4. **无参数时不显示行动按钮**：
     - 成型机 `TB2A1`（0359728000）因无推荐参数，行动建议列显示 `-`，杜绝空弹窗。

---

## 6. 重磅更新记录 (2026-09-07) - 代码库与部署全面治理、开机自启与一键免重载推送闭环

### 1. 本地与服务器代码库深度治理与精简
- **彻底删除 55+ 个非生产测试/排查脚本**：
  - 本地根目录与服务器根目录彻底删除了 32 个历史排查、诊断与单点测试脚本（`inspect_*.py`, `test_*.py`, `verify_*.py`, `check_dates.py`, `restart_backend.py` 等），清理了误重定向垃圾碎片（`Frontend`, `无法连接后端`）；
  - `backend/` 目录彻底清理了 28 个历史补丁脚本（`update_cpk_v2.py` 等）、特定日期脚本（`calc_cgrs_day_*.py`）及 4 个废弃的 12KB 空库文件；
  - 服务器 `scripts/` 目录彻底删除了 11 个废弃/重复/乱码批处理文件。
- **关键生产依赖绝对保护**：
  - 严谨排查发现 `run_daily_cgrs_export.bat` 依赖 `etl/export_cgrs_parquet.py`，完整保留了 `etl/` 目录并将该脚本备份至本地代码库；
  - 修改 `backend/main.py` 静态文件路径解析（`FRONTEND_DIST`），智能优先挂载 `frontend/dist`，使服务器安全移除根目录重复的 `dist/` 文件夹。

### 2. Windows 生产级开机自启动体系 (NSSM + Task Scheduler)
- **Nginx Web 服务 (Port 8088)**：通过 NSSM 注册为 Windows 系统自启服务 (`Nginx-Service`, `SERVICE_AUTO_START`)；
- **FastAPI 后端服务 (Port 8000)**：通过 NSSM 注册为 Windows 系统自启服务 (`FastAPI-Service`, `SERVICE_AUTO_START`)，日志重定向至 `logs/fastapi/`，异常退出 1 秒自动复活；
- **ETL 增量调度**：注册为 Windows 任务计划程序 `ETL_JOB`，每 30 分钟无窗口静默执行增量清洗流水线；
- **一键安装工具**：编写并部署了 `scripts/install_all_services_autostart.bat`，服务器端右键管理员运行一次即可永久生效，服务器通电 10 秒内无须人工登录即可全量拉起。

### 3. 本地一键自动构建发布闭环 (方案 B)
- **生产白名单精准同步**：重构 `deploy_to_server.py`，仅同步生产必需代码与配置，杜绝测试代码推向服务器；
- **优雅自重启与健康自愈**：
  1. 本地构建 Vue 生产包并安全同步文件；
  2. 向服务器发送 `POST /api/system/restart` 触发重启；
  3. NSSM 守护进程在 1 秒内重启加载最新 Python 进程；
  4. 发布脚本自动进行 20 秒健康轮询（每秒检测一次 `/api/articles/all`），确认就绪后触发 DuckDB 内存表热加载 (`/api/etl/reload`)；
  5. 校验前端 Nginx 访问正常；
- **本地快捷入口**：根目录新增 `一键部署到服务器.bat`，双击即可完成本地打包到远端生效的全部流程，彻底告别远程桌面手动重启。

### 4. 统计口径全链路统一：左侧核心行动表与右侧工序桑基图完全对齐 (2026-09-07)
- **问题排查根因**：
  - 左侧行动表 (`/api/articles/warning-cpk`) 使用工厂标准工业班次定义：`tu_first_loc_timestamp - INTERVAL 8 HOUR`（当天 08:00 至次日 08:00 为一个工业生产日）；
  - 右侧工序桑基图 (`/api/machines/process-sankey`) 历史代码使用 `COALESCE(tu_first_shift_date, tu_first_loc_timestamp, gt_loc_timestamp)` 且此前 `tu_first_shift_date` 字段初始化时使用的是自然日截断（00:00~23:59），导致未在 TU 终检的成型胎被 GT 戳混入、且跨班次轮胎被双重放大（如 0311573010 规格在 2026-09-07 当天左侧排产条数 $N=28$，右侧桑基图却拉取了 142 条自然日胎）。
- **统一改造闭环**：
  1. **底层内存表数据列口径彻底纠正**：在 `backend/main.py` 的 `reload_duckdb_data()` 中，将 `tu_first_shift_date` 的计算统一锁定为 `STRFTIME(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')`，确保所有依赖此字段的机台趋势、CPK 统计和桑基图天然遵循 8 点工业班次；
  2. **桑基图与预警机台过滤对齐**：移除桑基图中与 `gt_loc_timestamp` 的 COALESCE 兜底，严格按目标班次 `tu_first_shift_date::DATE = ?::DATE` 过滤，同时添加 `{ind_col} IS NOT NULL` 保证只有真正被质检并计入左侧 CPK 计算的轮胎才进入工序流向；
  3. **实测与校验**：
     - `2026-09-07`：左侧行动表 $N=28$，右侧桑基图总流向精确为 **28 胎**（TB285 分流至 CUG12: 11, CUG11: 2, CUG03: 11, CUG20: 4，合计 28）；核心瓶颈机台精准锁定为 `CUG11`；
     - `2026-09-06`：左侧行动表 $N=378$，右侧桑基图总流向精确为 **378 胎**；
     - 本地与远程生产服务器 (`\\10.246.97.159`) 已完成热部署和双向验证。

---

## 8. 重磅更新记录 (2026-09-08) - 核心规格行动表 UI 视觉与黄色风格统一重构

### 1. 设计规范遵照与品牌主色调统一 (Design-MD)
- **品牌主色调锁定**：全局统一为**琥珀金 / 暖黄色调 (Warm Amber Gold)**，告别原 Element Plus 默认冷蓝胶囊，彻底对齐系统大厅与工业看板的高端典雅视觉。
- **顶部操作区重塑**：
  - **聚焦规格标签 (`.spec-focus-badge`)**：由冷蓝 Tag 改为微光象牙暖金胶囊（`#fffbeb` 浅琥珀底色 + `#fde68a` 柔金细边框 + `#b45309` 强调文字）。
  - **单规格折线图主按钮 (`.btn-warm-primary`)**：升级为暖金渐变按钮（`linear-gradient(135deg, #f59e0b 0%, #d97706 100%)`），Hover 带有 `box-shadow: 0 4px 12px rgba(245, 158, 11, 0.35)` 琥珀弥散微光。
  - **查看全量轮廓按钮 (`.btn-warm-outline`)**：白底配 `#fde68a` 柔金边与琥珀文字，Hover 上浮 1px 并透出浅金底色。
- **Alert 联动提示条 (`.alert-banner`)**：
  - 彻底移除了原先的生硬浅冷蓝框（`#f0f7ff` / `#bfdbfe`），替换为象牙暖金微渐变（`linear-gradient(135deg, #fffdf5 0%, #fffbeb 100%)`）；
  - 左侧内嵌 `3px solid #f59e0b` 金色识别竖条与呼吸状态圆点，文字采用深琥珀金（`#92400e`）与深暖棕（`#78350f`），视觉层次分明。
- **表格行动措施列与交互**：
  - **“查看推荐参数”按钮 (`.action-btn`)**：由冷蓝胶囊改为琥珀金轻量胶囊按钮（`#fffbeb` 底 + `#fde68a` 边 + `#b45309` 字），Hover 产生琥珀微光投影。
  - **选中行高亮 (`.row-selected`)**：象牙金底色 `#fffbeb`，首列内嵌 `4px` 琥珀光条（`box-shadow: inset 4px 0 0 #f59e0b`），高亮文字转为 `#92400e`。
  - **代码与徽标**：规格编码 Hover 转为 `#d97706` 暖金；“新上线”胶囊换用暖黄底金边；数据加载 Loading 动画图标统一为 `#f59e0b` 暖金。

---

## 9. 重磅更新记录 (2026-09-08) - 系统重构方案 Q1–Q4 本地全面落地与架构瘦身

> **部署状态声明**：本次 Q1–Q4 改造及测试**严格在本地代码库执行，未向服务器发布任何文件**。待本地联调与用户验收通过后再推进生产发布。

### 1. Q1：统一 USL 规格上限为一个标准体系（优化后算法）
- **核心痛点**：原 `warning-cpk` 与 CPK 趋势等接口的内联 SQL CASE 中遗漏了 `GROUP 4` 分支，导致无显式 standard 记录的 GROUP 4 规格计算出的 USL 为空、CPK 异常缺失。
- **优化决策**：避免采用 Python N+1 逐行循环调用 `get_spec_usl`（会引发全厂大数据查询严重卡顿），改为直接在 DuckDB 向量化 SQL 中补齐 `GROUP 4` 分支（`rfpp: 14.5, rfh1: 10.0`），性能保持毫秒级，计算口径与 `get_spec_usl` 100% 对齐。
- **涉及端点**：
  1. `/api/articles/warning-cpk`（backend/main.py）
  2. `/api/articles/lot-barcode-detail`（backend/main.py）
  3. `/api/articles/lot-cpk-trend`（单规格下钻与全厂综合两个查询分支）

### 2. Q2：组合树 CPK 计算口径标准化与车间操作习惯保护
- **核心改进**：
  - 提取纯逻辑 Composable [`src/composables/useCpk.js`](file:///d:/Ava/untitled1/untitled1_v2/src/composables/useCpk.js)，输出 `calcCpk`（截断区间标准化为 `[-5, 5]`，`std <= 1e-6` 容错返回 1.33）与 `calcCombinedCpk`（加权合并均值与方差）；
  - 后端 `/api/machines/combination-tree` 返回的叶子节点增加预计算 `item["cpk"]`（仅对非 weight 指标计算）；
  - 前端 [`MachineCombinationTree.vue`](file:///d:/Ava/untitled1/untitled1_v2/src/components/charts/MachineCombinationTree.vue) 叶子优先读取 `p.cpk`，聚合节点采用加权方差合并后再计算标准 CPK；
  - **重要业务保护**：`weight`（胎重）指标**100% 维持原有的“均值偏差%”逻辑不变**，不在前后端按 CPK 双侧公差篡改，完全尊重车间操作工看盘习惯。
  - 生成独立变更日志 [`docs/change_log_Q2_combination_tree.md`](file:///d:/Ava/untitled1/untitled1_v2/docs/change_log_Q2_combination_tree.md)。

### 3. Q3：彻底清理废弃深度诊断面板、死 DOM 与孤儿文件
- **前端删除 12 个废弃/孤儿组件与模板残留**：
  - `src/components/panels/DiagnosticsPanel.vue`（原 Tab 3 诊断面板，后端接口早已注释）
  - `src/components/panels/InsightsPanel.vue`（原智能诊断预警卡片，已被 Row 1 替代）
  - `src/components/charts/LotCompareChart.vue`（诊断面板内部废弃图表）
  - `src/components/charts/MachineChart.vue`、`src/components/charts/ArticleBarChart.vue`、`src/components/tables/MachineCpkTable.vue`、`src/components/dialogs/MachineCpkTrendDialog.vue`（全工程 0 引用的历史遗留孤儿组件）
  - `src/components/layout/Sidebar.vue`、`src/components/filters/GlobalFilter.vue`
  - Vite 初始残留（`HelloWorld.vue`, `TheWelcome.vue`, `WelcomeItem.vue`, `icons/`）
- **瘦身 [`Dashboard.vue`](file:///d:/Ava/untitled1/untitled1_v2/src/views/Dashboard.vue)**：
  - 彻底移除了 Row 2（`InsightsPanel`）与 Row 4（路径聚类与诊断）两个 `v-if="false"` 占位死区块；
  - 清理了 160 余行无用 CSS（`.row4-custom-tabs`、`.cluster-tab-*`、`.step-*`、`.machine-tag-btn` 等）；
  - 清理了相关状态与方法（`row4ActiveTab`, `pathsData`, `combinations`, `loadPaths`, `loadCombinations`, `handleMachineJump`, `loadInsights`, `loadTrend`, `selectedWorkcenter`）；
  - 单文件从 **1880 行精简至 1270 行**（瘦身 **32%**）。
- **清理 [`src/api/index.js`](file:///d:/Ava/untitled1/untitled1_v2/src/api/index.js)**：
  - 剔除了 14 个断链或无人调用的历史接口（`getSummary`, `getDailyTrend`, `getWeeklyTrend`, `getArticles`, `getArticleTrend`, `getInsights`, `getSuspects`, `getJointCombinations`, `getLotDiagnosis`, `getPaths`, `getMachineCpk`, `getFilterArticles`, `getDateRange`, `getBestTuMachine`）。

### 4. Q4：删除 `/api/machines` 接口与清洗数据表硬编码异常标记
- **后端清理**：
  - 从 [`backend/main.py`](file:///d:/Ava/untitled1/untitled1_v2/backend/main.py) 中彻底删除已废弃的 `@app.get("/api/machines")` 路由（约 280 行代码）及无引用的 `diagnose_machine` 辅助函数。
- **前端清理**：
  - 移除了 `Dashboard.vue` 内 `loadMachines()` 轮询请求、`machines` 状态及未使用的 `machineChartHeight` 计算属性。
- **ETL 清洗脚本清理**：
  - 在 [`backend/etl/clean_data.py`](file:///d:/Ava/untitled1/untitled1_v2/backend/etl/clean_data.py) 的两处输出 SQL 中，移除了硬编码为 0 的 `0 AS rfpp_anomaly`, `0 AS rfh1_anomaly`, `0 AS grade_anomaly` 冗余列。

---

## 10. 当前系统状态与验证

- **前后端运行状态**：
  - 后端 FastAPI 服务（端口 8000）：常驻运行，DuckDB 载入 154.8 万条数据，717 个可用规格。
  - 前端 Vite 服务（端口 5173）：正常运行，`npm run dev` 正常热更新。
- **本地自动化构建与校验**：
  - **前端编译打包 (`npm run build`)**：**1.43 秒**成功通过，0 错误构建。
  - **后端代码语法校验 (`python -m py_compile`)**：`backend/main.py` 与 `backend/etl/clean_data.py` 均为 **0 错误**。
  - **本地接口冒烟测试**：
    - 已删除接口 `/api/machines`：访问返回 **404 Not Found**（符合预期）。
    - 活跃核心接口（`/api/articles/all`, `/api/trend/cpk`, `/api/machines/combination-tree` 等）：全部返回 **200 OK**。
- **部署状态**：
  - ⚠️ **严格按用户指示，当前所有改动仅在本地，未执行发布脚本**。待本地验证完成后再推送至服务器 `\\10.246.97.159`。
- **相关核心文件**：
  - 重构计划与执行记录：[docs/refactor_plan_Q1_Q4.md](file:///d:/Ava/untitled1/untitled1_v2/docs/refactor_plan_Q1_Q4.md)
  - 组合树 CPK 变更日志：[docs/change_log_Q2_combination_tree.md](file:///d:/Ava/untitled1/untitled1_v2/docs/change_log_Q2_combination_tree.md)
  - CPK 统一函数库：[src/composables/useCpk.js](file:///d:/Ava/untitled1/untitled1_v2/src/composables/useCpk.js)
  - 改造后看板主视图：[src/views/Dashboard.vue](file:///d:/Ava/untitled1/untitled1_v2/src/views/Dashboard.vue)
  - 改造后精简接口模块：[src/api/index.js](file:///d:/Ava/untitled1/untitled1_v2/src/api/index.js)
  - 后端主服务：[backend/main.py](file:///d:/Ava/untitled1/untitled1_v2/backend/main.py)
  - ETL 流水线清洗：[backend/etl/clean_data.py](file:///d:/Ava/untitled1/untitled1_v2/backend/etl/clean_data.py)
  - 全局记忆日志：[MEMORY_SUMMARY.md](file:///d:/Ava/untitled1/untitled1_v2/MEMORY_SUMMARY.md)

---

## 11. 重磅更新记录 (2026-09-08) - 后端 CPK 全口径彻底归一化（消灭全部遗留的 [0, 5] 截断与内联旧公式）

> **部署状态声明**：本次 CPK 统一改造及测试**严格在本地代码库执行，未向服务器发布任何文件**。

### 1. 核心排查与统一背景
用户排查发现：全站 CPK 口径统一过程中，在后端 `backend/main.py` 仍有数处残留使用旧版内联公式 `max(0.0, min(5.0, ...))`，导致负 CPK 被粗暴压成 0，与统一的 `[-5.0, 5.0]` 语义脱节。经全局深度排查，对全部 5 处遗留函数与相关预警阈值完成全面统一：

| 序号 | 所在函数/位置 | 业务场景 | 改前问题 | 改后方案 |
|---|---|---|---|---|
| 1 | `compute_machine_all_weighted_cpk` (line ~2565) | 综合机台 CPK 序列计算 | 使用 `max(0.0, min(5.0, cpk_i))` | 改用 `calc_cpk(m_v, s_v, spec_usl)` |
| 2 | `get_machines_cpk` (lines ~2840-2950) | 单规格/综合规格机台 CPK 及历史预警对比序列 | 4 处使用 `max(0.0, min(5.0, ...))` 计算 `spec_cpk`, `multi_cpk`, `c_v` | 统一改为 `calc_cpk(...)`，阈值下限设为 `max(-5.0, ...)` |
| 3 | `get_best_tu_machine_for_spec` (line ~4357) | 选最佳终检 TU 机台 | 使用裸除法未走保护与标准 clamp | 改用 `calc_cpk(avg_v, std_v, global_usl)` |
| 4 | `get_machine_best_process_sankey` (lines ~4433-4435) | 遴选最佳全流程路线评分 | 使用 `max(0.0, min(5.0, cpk_val))` 算质量分 | 改用 `calc_cpk(avg_v, std_v, global_usl)` |
| 5 | `get_machine_drilldown_combination_data` (lines ~5418, ~5436) | 工序下钻单规格/多规格对比 | 2 处使用 `max(0.0, min(5.0, ...))` 算 `s_cpk`, `m_cpk` | 统一改为 `calc_cpk(...)` |

### 2. 成果与验证
- **遗留清零**：在 `backend/main.py` 中对 `max(0.0` 进行全词搜索，结果由原来的 7 处降为 **0 处**；`min(5.0` 仅保留在 `calc_cpk` 核心唯一定义内（Line 532, 535）。
- **口径 100% 对齐**：
  - 单侧上限 CPK：`max(-5.0, min(5.0, (usl - mean) / (3.0 * std)))`
  - 双侧公差 CPK：`max(-5.0, min(5.0, min(cpu, cpl)))`
  - `std <= 1e-6` 容错值：统一返回 `1.33`。
- **验证通过**：
  - 后端 Python 编译校验 `python -m py_compile backend/main.py`：**0 错误**。
  - 前端打包构建 `npm run build`：**1.54s 成功，0 错误**。
- **严格承诺**：所有修改纯属**本地环境**，未向远程服务器推送。

---

## 12. 重磅更新记录 (2026-09-09~09-10) - 看板动态交互式漫游新手引导 (Spotlight Onboarding Tour)

> **分支隔离与架构保护声明**：
> 1. 本次功能完全工作在独立 Git 分支 `feature/kanban-onboarding-tour`，严格与 `main` 主分支解耦；
> 2. 严格遵循用户要求，**坚决不将新代码写入正在按模块重构的 `backend/routers`、`backend/services` 或 `backend/core` 架构**；
> 3. 后端数据支持完全自包含在单一独立文件 [backend/tutorial_standalone.py](file:///d:/Ava/untitled1/untitled1_v2/backend/tutorial_standalone.py) 中。

### 1. 核心功能与 5 步引导闭环
- **底层选型**：引入轻量级 `driver.js` (^1.8.0)，以深色半透明遮罩 + 聚光灯流体形变（Morphing Transition）+ 呼吸高光光环，实现高质感新手教学；
- **5 步引导业务闭环**：
  1. `Step 1`: `#tour-header-filters`（顶部全局控制栏：规格、时间、班组、指标维度切换与公差调节）；
  2. `Step 2`: `#tour-cpk-trend`（整体加权 CPK 控制图与 SPC 控制限，演示点击日期全屏数据联动）；
  3. `Step 3`: `#tour-spec-action-table`（核心规格行动表：三级预警机制与负向拉低贡献降序排查，演示下钻联动）；
  4. `Step 4`: `#tour-process-sankey`（单日工序流转与瓶颈机台诊断：成型/硫化/检测分流与发光红圈机台，及最佳生产路径与组合分析入口）；
  5. `Step 5`: `#tour-help-trigger`（顶栏常驻「💡 新手引导」快捷胶囊，支持随时重温与温习）；
- **持久化策略**：基于 `localStorage` (`has_seen_kanban_tour_v1`) 记录已读状态，首次进入延迟 1000ms 自动弹出，已看用户不重复弹窗。

### 2. 关键 Bug 诊断与镂空通透性修复
- **排查根因**：Driver.js 的镂空原理是在全屏 `<svg class="driver-overlay">` 内部通过 `<path fill-rule="evenodd">` 挖出透明矩形。此前 CSS 定制中向 `.driver-overlay` 根标签设置了 `background-color: rgba(...)` 和 `backdrop-filter`，导致整张 SVG 画布本身被刷上底色盖住了镂空区域；
- **修复措施**：
  - 在 [src/assets/tour.css](file:///d:/Ava/untitled1/untitled1_v2/src/assets/tour.css) 中将 `.driver-overlay` 设为 `background: transparent !important`，确保底布绝对透明；
  - 在 [src/composables/useDashboardTour.js](file:///d:/Ava/untitled1/untitled1_v2/src/composables/useDashboardTour.js) 中配置 `overlayColor: '#0f172a'`, `overlayOpacity: 0.72`, `stagePadding: 6`, `stageRadius: 10`, `popoverOffset: 12`；
  - 为 `.driver-popover` 设置 `z-index: 2147483647 !important` 与纯白背景 `background-color: #ffffff !important`；
- **实测验证**：高亮镂空区域 100% 通透纯白无阴影，卡片阴影质感极佳，5 步流体形变转场与销毁退出均顺利通过浏览器自动化及人工截屏验证。

### 3. 核心变更文件清单
- **样式定制**：[src/assets/tour.css](file:///d:/Ava/untitled1/untitled1_v2/src/assets/tour.css)
- **漫游逻辑 Composable**：[src/composables/useDashboardTour.js](file:///d:/Ava/untitled1/untitled1_v2/src/composables/useDashboardTour.js)
- **界面集成**：[src/App.vue](file:///d:/Ava/untitled1/untitled1_v2/src/App.vue)、[src/views/Dashboard.vue](file:///d:/Ava/untitled1/untitled1_v2/src/views/Dashboard.vue)
- **依赖项**：[package.json](file:///d:/Ava/untitled1/untitled1_v2/package.json)（添加 `driver.js: ^1.8.0`）
- **独立后端服务文件**：[backend/tutorial_standalone.py](file:///d:/Ava/untitled1/untitled1_v2/backend/tutorial_standalone.py)
- **计划与验收文档**：[implementation_plan.md](file:///C:/Users/uif77331/.gemini/antigravity-ide/brain/1cf48e1e-a453-4015-921e-c5b8845a34ac/implementation_plan.md)、[walkthrough.md](file:///C:/Users/uif77331/.gemini/antigravity-ide/brain/1cf48e1e-a453-4015-921e-c5b8845a34ac/walkthrough.md)
