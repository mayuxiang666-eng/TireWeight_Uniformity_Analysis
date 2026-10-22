# 07. 系统运维部署、排错手册与红线守则 (DevOps & Troubleshooting)

---

## 1. 生产环境局域网部署架构与自愈脚本

系统采用了**局域网共享服务器自动化部署架构**，主工程代码与生产发布流程高度规范化：

```mermaid
graph LR
    Dev["本地工作区<br>d:/Ava/untitled1/untitled1_v2"] -->|运行 deploy_to_server.py| Build["npm run build<br>编译前端静态产物 dist/"]
    Build -->|Windows SMB 协议| Server["10.246.97.159 共享服务器<br>tu ai/TireWeight_Uniformity_Analysis"]
    Server -->|NSSM Windows 服务守护| App["FastAPI 后端 8088 端口自愈热重启"]
    App -->|HTTP 200 探针| Check["健康检查测试与就绪确认"]
```

### 1.1 一键部署脚本 (`deploy_to_server.py` / `一键部署到服务器.bat`)
在本地根目录下双击运行 `一键部署到服务器.bat`，脚本将自动串联执行：
1. **前端自动化构建**：调用 `npm run build`，生成高压缩混淆的静态资源至 `dist/`；
2. **差异化增量覆盖**：将更新后的 `backend/`、`dist/`、`docs/` 及配置文件同步推送到服务器共享目录 `\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis`；
3. **远端服务优雅重启**：触发远端 Windows 守护服务重启并执行 `/api/system/restart`；
4. **探针健康检查**：轮询 `http://10.246.97.159:8088/api/etl/status` 直至返回正常状态。

---

## 2. 配置文件与加密安全规范

系统配置统一归档于 `backend/config/`，维护人员须妥善保护：
* `backend/config/db_config.json`：存储 Redshift 数据库的主机、端口与加密用户名/密码；
* `backend/config/secret.key`：32 位对称 XOR 混淆密钥，严禁提交到公共代码仓或明文分发；
* `backend/config/etl_state.json`：持久化记录增量同步的上次水位线时间戳，防止断点重启时全量重拉。

---

## 3. 常见疑难故障排查速查表 (Troubleshooting SOP)

| 故障现象 | 常见根因剖析 | 标准排查与自愈处理流程 (SOP) |
| :--- | :--- | :--- |
| **现象 1：启动报错找不到 Parquet 文件或 DuckDB clean_yield 表不存在** | 数据目录路径配置不匹配，或首次部署未初始化执行 ETL。 | 1. 检查 `backend/data/` 目录下是否存在 `yield_flat_table_joined_100_cleaned.parquet`；<br>2. 若不存在，在终端运行 `python backend/etl/clean_data.py` 手动清洗生成；<br>3. `backend/core/config.py` 内置了 6 级候选路径自动探测，确保各环境自适应识别。 |
| **现象 2：CGRS 展开面板显示 0 条有效路径，切换按钮置灰** | 1. 调参时间戳跨天错误合并导致改前样本被截断；<br>2. 某工序路径样本量 $< 5$ 胎；<br>3. 改前改后样本失衡比超过 2.5 倍。 | 1. 查看后端日志输出的 `path_summary`；<br>2. 确认该机台在调参日前后是否有足够生产批次；<br>3. 检查是否满足 $N_{\text{before}} \ge 5$ 且 $N_{\text{after}} \ge 5$，失衡比 $> 2.5$ 属于算法主动风控剔除，属于正常业务保护。 |
| **现象 3：DuckDB 内存报警或 Out of Memory Allocation Failure** | 批量并发统计查询超载，或临时磁盘目录所在分区空间已满。 | 1. 检查 `backend/data/duckdb_tmp/` 目录所在磁盘剩余空间是否大于 10GB；<br>2. 检查 `backend/core/db.py` 中 `PRAGMA max_memory='4GB'` 是否生效；<br>3. 可在操作系统临时清空 `duckdb_tmp` 目录下的孤立缓存文件。 |
| **现象 4：推荐参数出现成型推荐硫化、或三期推荐四期机台** | 机台分期缓存未命中或模糊匹配边界放宽。 | 1. 检查 `backend/core/time_utils.py` 中的 `init_machine_phase_cache`；<br>2. 成型机推荐必须包含断言 `get_machine_phase(peer_mach) == target_phase`；<br>3. 确认规格是否严格锁定为前 7 位 `spec_prefix7`，绝不允许使用前 5 位模糊匹配。 |

---

## 4. 架构开发与数据维护红线 (防劣铁律)

> [!CAUTION]
> **维护与二次开发红线守则 (绝对禁止违背)**：
> 1. **严禁人工硬编码伪造公差限值**：规格在 `Recipes.csv` 中未配置 USL/LSL 时，直接不计入 CPK，坚决不设任何假默认值！
> 2. **严禁跨工段与跨分期推荐**：成型设备（TB/GT）只能与成型比选，硫化设备（CU/CT）只能与硫化比选；三期设备严禁与四期设备混选推荐！
> 3. **严禁未来数据时间穿越**：在查询任何历史日期的质量和机台状态时，检索范围强制锁定为 `[target_date - 30天, target_date]`，绝对杜绝未来数据对历史观察日的数据污染！
> 4. **严禁在核心层引入反向依赖**：`backend/core/` 严禁反向 import `backend/services/`，保证纯函数核心层永远清洁、轻量、可测试。
