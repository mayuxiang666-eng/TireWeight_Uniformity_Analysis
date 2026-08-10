# 新清洗数据源字段与样本对比表 (转置视图)

本文件基于新数据源 `yield_flat_table_joined_0713_cleaned.parquet` 提取了3个典型业务样本进行转置并排对比，以便与项目前端开发人员快速对齐数据结构、字段命名、数值类型和取值示例。

## 样本选择说明
* **样本 1 (正常胎)**: 各项指标正常的轮胎记录 (`grade_anomaly = 0`)。
* **样本 2 (RFPP 异常)**: RFPP 物理测试项异常的轮胎记录 (`rfpp_anomaly = 1`，缺陷代码包含 `90A`)。
* **样本 3 (RFH1 异常)**: RFH1 物理测试项异常的轮胎记录 (`rfh1_anomaly = 1`，缺陷代码包含 `90B`)。

---

| 字段名称 (Column Name) | 样本 1 (正常) | 样本 2 (RFPP 异常) | 样本 3 (RFH1 异常) | 数据类型 (Arrow) | 业务定义与前端对齐建议 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `article_key` | `0316202` | `0316202` | `0315980` | `large_string` | 规格前7位编码标识 (即 `article10` 的前7位) |
| `article10` | `0316202079` | `0316202079` | `0315980000` | `large_string` | 产品10位规格代码 |
| `barcode` | `8508451844` | `8508451915` | `8524328147` | `large_string` | 轮胎唯一条码 (数据源唯一主键) |
| `anomaly_code` | `48` | `48` | `02BD` | `large_string` | 首位主缺陷异常代码 |
| `anomaly_code_1` | `*无*` | `90A` | `90B` | `large_string` | 辅助缺陷异常代码 1 (例如：`90A` 代表 RFPP 异常，`90B` 代表 RFH1 异常) |
| `anomaly_code_2` | `*无*` | `*无*` | `*无*` | `large_string` | 辅助缺陷异常代码 2 |
| `anomaly_code_3` | `*无*` | `*无*` | `*无*` | `large_string` | 辅助缺陷异常代码 3 |
| `ccs_workcenter` | `TB1A3` | `TB1A3` | `*无*` | `large_string` | 前工序 CCS 加工机台 (可能为空) |
| `gt_workcenter` | `TB2A3` | `TB2A3` | `TB234` | `large_string` | 前工序 GT 加工机台 |
| `ct_workcenter` | `CUJ15` | `CUJ07` | `CUH01` | `large_string` | 前工序 CT 成型加工机台 |
| `ct_shiftdate` | `2026-06-15 00:00:00` | `2026-06-26 00:00:00` | `2026-07-10 00:00:00` | `timestamp[ms]` | 成型生产班次日期 (时间戳，前端展示需格式化) |
| `bead_lot` | `992L05HLPR5N2` | `992LEQ3ENFFIB` | `*无*` | `large_string` | 胎圈材料批次 (可能为空) |
| `bead_workcenter` | `BA217` | `BA212` | `*无*` | `large_string` | 胎圈生产机台 (可能为空) |
| `tread_lot` | `992LEN0ANC6OY` | `992LEN09NFJ6B` | `*无*` | `large_string` | 胎面材料批次 (可能为空) |
| `tread_workcenter` | `EX108` | `EX108` | `*无*` | `large_string` | 胎面挤出机台 (可能为空) |
| `inner_liner_lot` | `992LENS2NC3U6` | `992LENS2NFJPT` | `*无*` | `large_string` | 气密层材料批次 (可能为空) |
| `inner_liner_workcenter` | `CL203` | `CL203` | `*无*` | `large_string` | 气密层加工机台 (可能为空) |
| `sidewall_lot` | `992LEN0CNC40I` | `992LEN0CNFH1I` | `*无*` | `large_string` | 胎侧材料批次 (可能为空) |
| `sidewall_workcenter` | `EX108` | `EX108` | `*无*` | `large_string` | 胎侧加工机台 (可能为空) |
| `first_breaker_lot` | `992LCR3TNC80S` | `992LCR3TNFI10` | `*无*` | `large_string` | 带束层1材料批次 (可能为空) |
| `first_breaker_workcenter` | `CX241` | `CX241` | `*无*` | `large_string` | 带束层1加工机台 (可能为空) |
| `second_breaker_lot` | `992LCRVLNC80T` | `992LCRVLNFD34` | `*无*` | `large_string` | 带束层2材料批次 (可能为空) |
| `second_breaker_workcenter` | `CX242` | `CX242` | `*无*` | `large_string` | 带束层2加工机台 (可能为空) |
| `first_ply_lot` | `992LDW01NC7BU` | `992LDW01NFCBN` | `*无*` | `large_string` | 帘布层1材料批次 (可能为空) |
| `first_ply_workcenter` | `CX103` | `CX103` | `*无*` | `large_string` | 帘布层1加工机台 (可能为空) |
| `wound_cap_ply1_lot` | `992LDYBLNC1VD` | `992LDYBHNF2MB` | `*无*` | `large_string` | 冠带层1材料批次 (可能为空) |
| `wound_cap_ply1_workcenter` | `CX502` | `CX502` | `*无*` | `large_string` | 冠带层1加工机台 (可能为空) |
| `wound_cap_ply2_lot` | `992LDYBNNC1VD` | `992LDYBNNF2MB` | `*无*` | `large_string` | 冠带层2材料批次 (可能为空) |
| `wound_cap_ply2_workcenter` | `CX502` | `CX502` | `*无*` | `large_string` | 冠带层2加工机台 (可能为空) |
| `tb_first_workcenter` | `TB21` | `TB22` | `TB43` | `large_string` | TB 工序首次检测加工设备 |
| `tb_last_workcenter` | `TB21` | `TB22` | `TB43` | `large_string` | TB 工序最后一次加工设备 |
| `tg_first_workcenter` | `TG21` | `TG22` | `TG6` | `large_string` | TG 工序首次检测加工设备 |
| `tg_last_workcenter` | `TG21` | `TG22` | `TG3` | `large_string` | TG 工序最后一次加工设备 |
| `tu_first_workcenter` | `TU21` | `TU22` | `TU6` | `large_string` | TU 工序首次检测加工设备 |
| `tu_last_workcenter` | `TU21` | `TU22` | `TU3` | `large_string` | TU 工序最后一次加工设备 |
| `rfppwc_first` | `44.61095300` | `101.49226200` | `94.32561900` | `large_string` | RFPP 首次测试物理值 (数值型字符串，前端计算需转为 Float) |
| `rfh1wc_first` | `34.44312800` | `60.97095000` | `84.90210500` | `large_string` | RFH1 首次测试物理值 (数值型字符串，前端计算需转为 Float) |
| `specissue` | `001` | `001` | `001` | `large_string` | 工艺规格版本号 (配方 issue 版本) |
| `greentiregutsid` | `19723382` | `19723382` | `20367970` | `large_string` | 绿胎胎体组件 ID |
| `group` | `GROUP 1` | `GROUP 1` | `GROUP 1` | `large_string` | 分群组标签 (如：GROUP 1 / GROUP 2A / 2B / 3 / 4) |
| `last_modified_utc_timestamp` | `2026-05-18 05:29:19` | `2026-05-18 05:29:19` | `2026-06-09 05:19:51` | `timestamp[ms]` | 规格标准最后修改时间 (时间戳，前端展示需格式化) |
| `rn` | `1` | `1` | `1` | `large_string` | 去重排名标记 (新数据集中固定为 1) |
| `rfpp_anomaly` | `0` | `1` | `0` | `int64` | RFPP 测试项异常标记 (1: 异常, 0: 正常) |
| `rfh1_anomaly` | `0` | `0` | `1` | `int64` | RFH1 测试项异常标记 (1: 异常, 0: 正常) |
| `grade_anomaly` | `0` | `1` | `1` | `int64` | 综合质量异常标记 (1: 异常, 0: 正常，即 rfpp_anomaly \| rfh1_anomaly) |