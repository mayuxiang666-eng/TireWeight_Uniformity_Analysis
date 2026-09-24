import { nextTick } from 'vue'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import '../assets/tour.css'

const TOUR_STORAGE_KEY = 'has_seen_kanban_tour_v3'

let activeDriver = null
let onUserInteractCallback = null

/**
 * 动态点击动效指示器 DOM 管理
 */
function removeClickPointer() {
  const existing = document.getElementById('tour-dynamic-pointer')
  if (existing && existing.parentNode) {
    existing.parentNode.removeChild(existing)
  }
}

/**
 * 挂载动态点击指示器
 * @param {Element|string} anchorTarget 挂载目标节点或选择器
 * @param {string} labelText 提示文字
 * @param {Object} options 配置参数
 */
function renderClickPointer(anchorTarget, labelText, options = {}) {
  removeClickPointer()

  const el = typeof anchorTarget === 'string' ? document.querySelector(anchorTarget) : anchorTarget
  if (!el) return

  const rect = el.getBoundingClientRect()
  const pointerEl = document.createElement('div')
  pointerEl.id = 'tour-dynamic-pointer'
  pointerEl.className = 'tour-click-pointer-container'

  // 计算绝对居中定位坐标 (包含视口滚动)
  const topPercent = options.topPercent !== undefined ? options.topPercent : 0.5
  const leftPercent = options.leftPercent !== undefined ? options.leftPercent : 0.5
  const topPos = window.scrollY + rect.top + rect.height * topPercent + (options.offsetY || 0)
  const leftPos = window.scrollX + rect.left + rect.width * leftPercent + (options.offsetX || 0)

  pointerEl.style.top = `${topPos}px`
  pointerEl.style.left = `${leftPos}px`

  pointerEl.innerHTML = `
    <div class="tour-ripple-ring"></div>
    <div class="tour-ripple-ring"></div>
    <div class="tour-pointer-content">
      <span class="tour-pointer-emoji">👆</span>
      ${labelText ? `<span class="tour-pointer-tag">${labelText}</span>` : ''}
    </div>
  `

  // 绑定点击响应：点击指示器时直接触发元素点击并推进引导
  pointerEl.addEventListener('click', (e) => {
    e.stopPropagation()
    if (typeof options.onClick === 'function') {
      options.onClick()
    } else {
      el.click()
    }
  })

  document.body.appendChild(pointerEl)
}

/**
 * 看板交互式新手引导全新 4 步业务流程闭环定义
 * 极简紧凑数字序号风 + 大陆金橙黄配色风格
 * 流程：首先查看整体趋势 -> 然后定位核心预警规格 -> 排查全链路工序与落地改善措施 -> 闭环重温
 */
export const tourSteps = [
  {
    element: '#tour-cpk-trend',
    popover: {
      title: '📈 第一步：监测整体趋势，锁定异常日期',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>全局趋势监测</strong>：首先关注全厂加权 CPK 实时走势及 SPC 控制限，掌握整体质量平稳度。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>厂区与极值过滤</strong>：右上角可快速切换三四期厂区，或勾选「剔除 Top 10 预警规格」排除极值波动干扰。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">3</span>
            <div class="tour-point-text"><strong>锁定预警日期</strong>：寻找曲线上突破警戒限的红色预警标记点，点击即可展开当天深度分析。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">👆</span>
          <span>动效指引：请点击图中的预警红点，进入当日规格排查</span>
        </div>
      `,
      side: 'bottom',
      align: 'center'
    }
  },
  {
    element: '#tour-spec-action-table',
    popover: {
      title: '📋 第二步：定位核心预警规格，聚焦恶化源头',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>定位下拉规格</strong>：系统自动列出当日拉低全厂 CPK 的核心负贡献预警规格及关联机台。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>紧急程度排序</strong>：依据小球颜色判定处置优先级（🔴红色高优恶化 > 🟠橙色中度预警 > 🟡黄色关注）。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">3</span>
            <div class="tour-point-text"><strong>聚焦排查链路</strong>：点击目标预警规格，即可在右侧透视该规格当天的全流程工序流转图。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">👆</span>
          <span>动效指引：请点击该预警规格编号，展开右侧工艺流转图</span>
        </div>
      `,
      side: 'right',
      align: 'start'
    }
  },
  {
    element: '#tour-process-sankey',
    popover: {
      title: '🔄 第三步：排查全链路工序，落地改善措施',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>工序流转全景</strong>：透视该规格当日在「成型 ➔ 硫化 ➔ 检测」工序链路的实际物料流向。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>定位瓶颈机台</strong>：流转图中带红色阴影发光的节点即为主要恶化瓶颈机台，直指质量根因。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">3</span>
            <div class="tour-point-text"><strong>落地改善措施</strong>：对照左侧行动措施点击「查看推荐参数」，获取该机台历史最优工艺配方落地闭环改善。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">💡</span>
          <span>分析闭环：已完整掌握从全厂走势到单台机台推荐配方的诊断全流程</span>
        </div>
      `,
      side: 'left',
      align: 'start'
    }
  },
  {
    element: '#tour-help-trigger',
    popover: {
      title: '💡 完成探索：质量分析闭环已掌握',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>标准流程</strong>：你已熟练掌握「查看整体趋势 ➔ 定位预警规格 ➔ 排查工序机台 ➔ 查看推荐措施」的分析全链路！</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>随时唤起</strong>：日常工作中若需再次温习，随时点击顶栏的「新手引导」按钮即可重温。</div>
          </div>
        </div>
      `,
      side: 'bottom',
      align: 'end'
    }
  }
]

export function useDashboardTour() {
  /**
   * 平滑推进到下一步
   */
  const nextStep = () => {
    removeClickPointer()
    if (!activeDriver) return
    const isAct = typeof activeDriver.isActive === 'function' ? activeDriver.isActive() : true
    if (isAct) {
      setTimeout(() => {
        if (activeDriver && typeof activeDriver.moveNext === 'function') {
          activeDriver.moveNext()
        }
      }, 50)
    }
  }

  /**
   * 监听当前高亮步骤并精确定位手势
   */
  const handleStepHighlight = (element, step, { state }) => {
    removeClickPointer()

    const stepIndex = state?.activeIndex ?? -1

    if (stepIndex === 0) {
      // 步骤 1: 整体 CPK 控制图 - 手放红点正下方，朝上指 👆
      setTimeout(() => {
        const chartWrap = document.querySelector('#tour-cpk-trend .chart-wrap') || document.querySelector('#tour-cpk-trend .card-body')
        if (chartWrap) {
          renderClickPointer(chartWrap, '', {
            topPercent: 0.74,
            leftPercent: 0.405,
            offsetY: 8,
            onClick: () => {
              if (onUserInteractCallback) {
                onUserInteractCallback('select-warning-date')
              }
              nextStep()
            }
          })
        }
      }, 350)
    } else if (stepIndex === 1) {
      // 步骤 2: 核心规格行动表 - 仅保留手指和光圈，手放规格单元格下方朝上指 👆
      setTimeout(() => {
        const firstSpecTd = document.querySelector('#tour-spec-action-table .el-table__body-wrapper tbody tr:first-child td:first-child') ||
                            document.querySelector('#tour-spec-action-table .clickable-row td:first-child') ||
                            document.querySelector('#tour-spec-action-table .clickable-row')

        if (firstSpecTd) {
          renderClickPointer(firstSpecTd, '', {
            topPercent: 1.0,
            leftPercent: 0.5,
            offsetY: 8,
            onClick: () => {
              firstSpecTd.click()
              if (onUserInteractCallback) {
                onUserInteractCallback('select-spec-row')
              }
              nextStep()
            }
          })
        } else {
          renderClickPointer('#tour-spec-action-table', '', {
            topPercent: 0.35,
            leftPercent: 0.2,
            offsetY: 8,
            onClick: nextStep
          })
        }
      }, 350)
    }
  }

  /**
   * 启动新手漫游引导
   * @param {boolean} force 是否强制唤起
   * @param {Function} onAction 用户交互代理回调
   */
  const startTour = async (force = false, onAction = null) => {
    if (onAction) {
      onUserInteractCallback = onAction
    }

    if (!force) {
      const hasSeen = localStorage.getItem(TOUR_STORAGE_KEY)
      if (hasSeen === 'true') {
        return
      }
    }

    await nextTick()

    const firstEl = document.querySelector('#tour-cpk-trend')
    if (!firstEl) {
      setTimeout(() => startTour(force, onAction), 400)
      return
    }

    if (activeDriver) {
      activeDriver.destroy()
    }

    activeDriver = driver({
      showProgress: true,
      animate: true,
      allowClose: true,
      disableActiveInteraction: false,
      overlayColor: '#0f172a',
      overlayOpacity: 0.72,
      stagePadding: 6,
      stageRadius: 10,
      popoverOffset: 12,
      nextBtnText: '下一步 →',
      prevBtnText: '← 上一步',
      doneBtnText: '完成探索 🎉',
      progressText: '{{current}} / {{total}}',
      onHighlightStarted: handleStepHighlight,
      onDestroyStarted: () => {
        removeClickPointer()
        localStorage.setItem(TOUR_STORAGE_KEY, 'true')
        if (activeDriver) {
          activeDriver.destroy()
          activeDriver = null
        }
      },
      steps: tourSteps
    })

    activeDriver.drive()
  }

  /**
   * 供业务组件在用户点击对应元素后调用推进引导
   * @param {number} expectedStepIndex 当前步骤索引 (0: 趋势图日期点击, 1: 规格行点击)
   */
  const advanceTourIfActive = (expectedStepIndex = null) => {
    if (!activeDriver) return
    const isAct = typeof activeDriver.isActive === 'function' ? activeDriver.isActive() : true
    if (isAct) {
      const currIdx = activeDriver.getActiveIndex()
      if (expectedStepIndex === null || currIdx === expectedStepIndex) {
        nextStep()
      }
    }
  }

  /**
   * 重置已读状态
   */
  const resetTourState = () => {
    localStorage.removeItem(TOUR_STORAGE_KEY)
  }

  return {
    startTour,
    advanceTourIfActive,
    resetTourState,
    tourSteps
  }
}
