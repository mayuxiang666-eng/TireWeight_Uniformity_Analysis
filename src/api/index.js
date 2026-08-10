import axios from 'axios'

const BASE = 'http://127.0.0.1:8000'

const http = axios.create({
  baseURL: BASE,
  timeout: 120000,
})

export const api = {
  /** 总览摘要 */
  getSummary: () => http.get('/api/summary'),

  /** 日度趋势 */
  getDailyTrend: (article = null) =>
    http.get('/api/trend/daily', { params: article ? { article10: article } : {} }),

  /** 周度趋势 */
  getWeeklyTrend: (article = null) =>
    http.get('/api/trend/weekly', { params: article ? { article10: article } : {} }),

  /** 规格型号排行 */
  getArticles: (params = {}) => http.get('/api/articles', { params }),

  /** 预警规格型号排行 (CPK稳定值排行) */
  getWarningArticles: (params = {}) => http.get('/api/articles/warning-cpk', { params }),

  /** 全量规格型号列表 */
  getAllArticles: () => http.get('/api/articles/all'),


  /** 规格下钻日趋势 */
  getArticleTrend: (article) => http.get(`/api/articles/${encodeURIComponent(article)}/trend`),

  /** 工位机台异常排行 */
  getMachines: (params = {}) => http.get('/api/machines', { params }),

  /** 过滤用：规格列表 */
  getFilterArticles: (params = {}) => http.get('/api/filters/articles', { params }),

  /** 日期范围 */
  getDateRange: () => http.get('/api/filters/daterange'),

  /** 自动预警建议 */
  getInsights: (params = {}) => http.get('/api/insights', { params }),

  /** 嫌疑机台清单与诊断 */
  getSuspects: (params = {}) => http.get('/api/diagnose/suspects', { params }),

  /** 双机台联合风险 */
  getJointCombinations: (params = {}) => http.get('/api/diagnose/combinations', { params }),

  /** 物料批次诊断 */
  getLotDiagnosis: (params = {}) => http.get('/api/diagnose/lots', { params }),

  /** 工艺流转主导路径对比 */
  getPaths: (params = {}) => http.get('/api/diagnose/paths', { params }),

  /** CPK 趋势 */
  getCpkTrend: (params = {}) => http.get('/api/trend/cpk', { params }),

  /** 机台 CPK (avg + 3sigma) 数据 */
  getMachineCpk: (params = {}) => http.get('/api/machines/cpk', { params }),

  /** 机台 CPK 趋势下钻 */
  getMachineCpkTrend: (params = {}) => http.get('/api/machines/cpk/trend', { params }),

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
}
