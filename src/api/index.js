import axios from 'axios'

const BASE = ''

const http = axios.create({
  baseURL: BASE,
  timeout: 120000,
})

export const api = {
  /** 预警规格型号排行 (CPK稳定值排行) */
  getWarningArticles: (params = {}) => http.get('/api/articles/warning-cpk', { params }),

  /** 全量规格型号列表 */
  getAllArticles: () => http.get('/api/articles/all'),

  /** 规格期别信息 (三期/四期) */
  getArticlePhase: (article10) => http.get('/api/article/phase', { params: { article10 } }),

  /** CPK 趋势 */
  getCpkTrend: (params = {}) => http.get('/api/trend/cpk', { params }),

  /** 每日生产总量、正常量与TU/TG/TB异常聚合统计趋势 */
  getTrendProductionAnomaly: (params = {}) => http.get('/api/trend/production-anomaly', { params }),

  /** 成型机台 CGRS 参数变更记录查询 */
  getCgrsRecords: (params = {}) => http.get('/api/cgrs/records', { params }),

  /** 成型机台 CGRS 控制变量分析（路径拆分 CPK 对比） */
  getCgrsControlledAnalysis: (params = {}) => http.get('/api/cgrs/controlled-analysis', { params }),

  /** 生产工序流转路径桑葚图 */
  getMachineProcessSankey: (params = {}) => http.get('/api/machines/process-sankey', { params }),

  /** 全量数据集最佳生产工序流转路径 */
  getMachineBestProcessSankey: (params = {}) => http.get('/api/machines/best-process-sankey', { params }),

  /** 机台排列组合决策树路径 */
  getMachineCombinationTree: (params = {}) => http.get('/api/machines/combination-tree', { params }),

  /** 选中规格关联物料批次 (Lot) CPK 质量追溯曲线数据 */
  getLotCpkTrend: (params = {}) => http.get('/api/articles/lot-cpk-trend', { params }),

  /** 选中物料批次 (Lot) 下属 Barcode 级测量实际值分布数据 */
  getLotBarcodeDetail: (params = {}) => http.get('/api/articles/lot-barcode-detail', { params }),

  /** 指定规格在单日内全部单胎 (Barcode) 实际测量值时序数据 (Run Chart) */
  getBarcodeMeasurements: (params = {}) => http.get('/api/articles/barcode-measurements', { params }),

  /** CGRS 历史参数推荐（同工段近 7 天最优调参建议） */
  getParamRecommendation: (params = {}) => http.get('/api/cgrs/param-recommendation', { params }),

  /** 组合分析 - 机台 CPK 双线趋势对比 (单规格 vs 多规格) */
  getMachineCpkTrendComparison: (params = {}) => http.get('/api/machines/cpk-trend-comparison', { params }),

  /** Top N 负贡献度机台排名（当天及过去几天） */
  getTopWarningMachines: (params = {}) => http.get('/api/machines/top-warning', { params }),

  /** CGRS 智能参数推荐 (根据调参恶化或新上线推荐历史最佳/标杆参数) */
  getRecommendedCgrsParams: (params = {}) => http.get('/api/cgrs/recommended-params', { params }),
}

