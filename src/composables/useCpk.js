/**
 * 与后端 calc_cpk (backend/main.py:524) 逐行一致的 CPK 计算
 * - lsl 为 null/undefined 时单侧上限: (usl - mean) / (3 * std)
 * - lsl 存在时双侧: min((usl - mean)/(3*std), (mean - lsl)/(3*std))
 * - clamp 到 [-5, 5] (支持负值以如实反映超差严重程度)
 * - std <= 1e-6 时返回 1.33
 */
export function calcCpk(mean, std, usl, lsl = null) {
  if (std <= 1e-6) return 1.33
  if (lsl === null || lsl === undefined) {
    return Math.max(-5, Math.min(5, (usl - mean) / (3 * std)))
  }
  const cpu = (usl - mean) / (3 * std)
  const cpl = (mean - lsl) / (3 * std)
  return Math.max(-5, Math.min(5, Math.min(cpu, cpl)))
}

/**
 * 合并方差聚合后算 CPK（供组合树聚合节点使用）
 * rows: [{ lot_cnt, avg_val, std_val, cpk }]
 * - 合并均值/合并方差数学与现有 aggregateNodeStats 完全一致
 * - 对非 weight：用 calcCpk(combinedMean, combinedStd, usl, lsl)
 * - 对 weight：返回 combinedMean（保留"偏差%"语义，不变）
 */
export function calcCombinedCpk(rows, usl, lsl, indicator) {
  if (!rows || rows.length === 0) return 1.33
  const totalN = rows.reduce((a, r) => a + (r.lot_cnt || 0), 0)
  if (totalN <= 0) return 1.33
  const combinedMean = rows.reduce((a, r) => a + (r.lot_cnt || 0) * r.avg_val, 0) / totalN
  const combinedVar = rows.reduce((a, r) => {
    const diff = r.avg_val - combinedMean
    return a + (r.lot_cnt || 0) * (r.std_val * r.std_val + diff * diff)
  }, 0) / totalN
  const combinedStd = Math.sqrt(combinedVar)
  if (indicator === 'weight') {
    return combinedMean
  }
  return calcCpk(combinedMean, combinedStd, usl, lsl)
}
