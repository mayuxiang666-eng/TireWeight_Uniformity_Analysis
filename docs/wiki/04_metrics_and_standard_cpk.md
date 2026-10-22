# 04. 17项质检指标统一定义与标准 CPK 引擎 (Metrics & CPK Engine)

---

## 1. 17 项工序质检指标全景定义表

系统核心支持三大工段共 17 项高精质检指标及 1 项胎重物理指标，所有配置严格收敛于 `backend/core/cpk.py` 的 `INDICATORS_SPEC` 字典中：

| 工段分组 | 指标代码 | 指标中文全称 | 测量列 (`col`) | 配方上限列 (`usl_col`) | 配方下限列 (`lsl_col`) | 物理单位 | 缩放系数 (`scale`) | 公差类型 |
| :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **TU** | `rfpp` | RFPP 径向力峰峰值 | `rfppwc_first` | `standard_rfpp` | - | N (牛) | **10.0** | 单侧上限 |
| **TU** | `rfh1` | RFH1 径向力一次谐波 | `rfh1wc_first` | `standard_rfh1` | - | N (牛) | **10.0** | 单侧上限 |
| **TU** | `rfh2` | RFH2 径向力二次谐波 | `rfh2wc_first` | `standard_rfh2` | - | N (牛) | **10.0** | 单侧上限 |
| **TU** | `lfpp` | LFPP 侧向力峰峰值 | `lfppwc_first` | `standard_lfpp` | - | N (牛) | **10.0** | 单侧上限 |
| **TU** | `lfh1` | LFH1 侧向力一次谐波 | `lfh1wc_first` | `standard_lfh1` | - | N (牛) | **10.0** | 单侧上限 |
| **TU** | `cony` | CONY 锥度效应力 | `cony_first` | `conny_usl` | `conny_lsl` | N (牛) | **1.0** | **双侧公差** |
| **TU** | `plys` | PLYS 帘布层效应力 | `plys_first` | `plys_usl` | `plys_lsl` | N (牛) | **1.0** | **双侧公差** |
| **TG** | `tbul` | TBUL 上胎侧凸起 | `tbul_first` | `tbul_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TG** | `bbul` | BBUL 下胎侧凸起 | `bbul_first` | `bbul_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TG** | `tdep` | TDEP 上胎侧凹陷 | `tdep_first` | `tdep_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TG** | `bdep` | BDEP 下胎侧凹陷 | `bdep_first` | `bdep_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TG** | `tlro` | TLRO 上胎侧径向跳动 | `tlro_first` | `tlro_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TG** | `blro` | BLRO 下胎侧径向跳动 | `blro_first` | `blro_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TG** | `crro` | CRRO 胎冠径向跳动 | `crro_first` | `crro_usl` | - | mm (毫米) | **1.0** | 单侧上限 |
| **TB** | `tbalw`| TBALW 上侧动不平衡 | `tbalw_first` | `tbalw_usl` | - | g (克) | **1.0** | 单侧上限 |
| **TB** | `bbalw`| BBALW 下侧动不平衡 | `bbalw_first` | `bbalw_usl` | - | g (克) | **1.0** | 单侧上限 |
| **TB** | `sbalw`| SBALW 静不平衡 | `sbalw_first` | `sbalw_usl` | - | g (克) | **1.0** | 单侧上限 |
| **其他**| `weight`| 胎重均值偏差率 | `v_weight` | - | - | % (百分比) | **1.0** | 均值偏差率 |

---

## 2. 物理量纲、单位与缩放系数 (Scale)

在不同工业检测仪器中，原始采集的数值量纲各不相同，系统制定了严格的物理量纲转换规则：

1. **TU 工段力学指标 (RFPP, RFH1, RFH2, LFPP, LFH1)**：
   - 仪器原始标称值以**分牛 (daN)** 或标称等级倍数上传（如 `10.5` 对应 `105N`）；
   - 系统计算与看板呈现时，统一乘以缩放系数 `scale = 10.0`，转换为物理单位**牛顿 (N)**；
   - 例外项：`CONY` (锥度) 与 `PLYS` (帘布层效应) 原始存储即为标准牛顿 (N)，`scale = 1.0`。
2. **TG 几何尺寸指标 (TBUL, BBUL, TDEP, BDEP, TLRO, BLRO, CRRO)**：
   - 经 ETL 换算后存储为**毫米 (mm)**，配方限值 `_usl` 同样为毫米（如 `0.22mm`, `0.80mm`）；
   - **量纲完全一致，不需要再乘以 1000**。
3. **TB 动平衡指标 (TBALW, BBALW, SBALW)**：
   - 测量值与配方限 `_usl` 均为**克 (g)**（如 `12.18g`, `50.0g`）；
   - **量纲完全一致，不需要任何系数缩放**。

---

## 3. 配方公差 100% 严格遵循准则

> [!CAUTION]
> **开发与维护铁律：零伪造兜底原则**
> - 系统彻底废除了任何形式的人工硬编码假公差（如曾出现过的 `standard_rfpp = 105` 兜底）；
> - 某个轮胎规格在 `Recipes.csv` 配方表中若未配置该项公差限（即值为 `NULL`），代表该规格在工厂质量规范中**不考核该项质量特性**；
> - 系统判定如果 `usl_val is None and lsl_val is None`，**直接不将该规格纳入该指标的 CPK 统计**，坚决杜绝捏造假数据误导生产排查！

---

## 4. 单侧与双侧标准 CPK 纯函数实现

标准 CPK 计算函数位于 `backend/core/cpk.py:L96-119`。

### 4.1 数学公式
对于正态分布数据，设均值为 $\mu$，标准差为 $\sigma$：
* **单侧上限指标 (越小越好，如力学峰值、几何跳动、动平衡量)**：
  $$C_{pk} = C_{pu} = \frac{USL - \mu}{3\sigma}$$
* **双侧公差指标 (目标值居中，如 CONY, PLYS)**：
  $$C_{pu} = \frac{USL - \mu}{3\sigma}, \quad C_{pl} = \frac{\mu - LSL}{3\sigma}$$
  $$C_{pk} = \min(C_{pu}, C_{pl})$$

### 4.2 Python 代码实现与工程防呆
```python
# 代码位置：backend/core/cpk.py:L96-119
def calc_cpk(mean: Optional[float], std: Optional[float], usl: Optional[float], lsl: Optional[float] = None) -> Optional[float]:
    """统一计算单侧或双侧 CPK
    - 若 mean / std / usl 为空，返回 None
    - lsl 为 None 时：单侧上限 CPK = (usl - mean) / (3 * std)
    - lsl 存在时：  双侧 CPK = min((usl - mean)/(3*std), (mean - lsl)/(3*std))
    """
    if mean is None or std is None:
        return None
    if usl is None and lsl is None:
        return None
    # 极小方差保护：当机台产出极度稳定时（方差接近0），防止除以零异常
    if std <= 1e-6:
        return 1.33

    if lsl is None:
        if usl is None:
            return None
        # 数值截断保护：将极端离群值约束在 [-5.0, 5.0] 区间，避免界面图表坐标轴无限撑爆
        return max(-5.0, min(5.0, (usl - mean) / (3.0 * std)))
    else:
        if usl is None:
            return max(-5.0, min(5.0, (mean - lsl) / (3.0 * std)))
        cpu = (usl - mean) / (3.0 * std)
        cpl = (mean - lsl) / (3.0 * std)
        return max(-5.0, min(5.0, min(cpu, cpl)))
```

---

## 5. 8 小时生产时间偏移与全厂加权计算

### 5.1 8 小时工厂工作制位移
工厂采用**“三班两运转 / 三班倒”**工作制，排产周期的自然切分点通常是**早晨 08:00**（08:00~次日08:00 为一个完整生产日）：
* 如果直接按自然日（00:00~23:59）统计，会将同一个夜班的轮胎割裂在两天；
* 系统全局统一对终检时间戳执行 **减去 8 小时** 偏移：
  ```sql
  STRFTIME(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')
  ```

### 5.2 全厂加权综合 CPK 计算
工厂不能简单对不同规格的 CPK 进行算术平均（这会导致产 2 胎的小规格与产 2000 胎的主力规格拥有相同权重）。
全厂综合加权 CPK 严格按照**各规格合格样本排产条数 $N_i$ 作为权重**：
$$CPK_{\text{weighted}} = \frac{\sum_{i=1}^{M} (CPK_i \times N_i)}{\sum_{i=1}^{M} N_i}$$

* **样本过滤门槛**：单规格单日排产条数 $N_i < 5$ 的规格由于样本不足，不参与全厂加权统计，防止统计小样本偶然扰乱大盘。

---

> [!TIP]
> **下一章导航**：
> 掌握了指标与 CPK 基础后，请阅读 [05. 核心归因算法与 CGRS 控制变量模型](05_core_algorithms_deepdive.md)，探索产量平方根平滑、三级预警判定与 CGRS 路径拆分等高阶算法！
