import { nextTick } from 'vue'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import '../assets/tour.css'

const TOUR_STORAGE_KEY = 'has_seen_kanban_tour_v5'

let activeDriver = null
let onUserInteractCallback = null
let autoAdvanceTimer = null

// 步骤内微动画状态控制
let step1AnimState = 1 // 1: 提示点击柱形图, 2: 提示点击 CPK 波动
let step2AnimState = 1 // 1: 提示点击核心规格, 2: 提示点击推荐参数

/**
 * 注册用户交互代理回调 (供 Dashboard.vue 等业务组件调用)
 */
export function registerTourHandler(handler) {
  onUserInteractCallback = handler
}

/**
 * 外部通知：日期已被选中 (从图表点击或动效点击触发)
 */
export function notifyTourDateSelected() {
  if (activeDriver && activeDriver.getActiveIndex() === 0 && step1AnimState === 1) {
    triggerStep1Animation2()
  }
}

/**
 * 外部通知：规格已被选中 (从表格点击或动效点击触发)
 */
export function notifyTourSpecSelected() {
  if (activeDriver && activeDriver.getActiveIndex() === 1 && step2AnimState === 1) {
    triggerStep2Animation2()
  }
}

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
 * 等待指定 DOM 节点渲染且宽高展开完成 (专门用于弹窗等有 transition 动画的组件)
 */
function waitForDialogReady(selector = '.rec-param-dialog', timeout = 3000) {
  return new Promise((resolve) => {
    const start = Date.now()
    const timer = setInterval(() => {
      const el = document.querySelector(selector)
      if (el) {
        const rect = el.getBoundingClientRect()
        if (rect.width > 200 && rect.height > 100) {
          clearInterval(timer)
          resolve(el)
          return
        }
      }
      if (Date.now() - start > timeout) {
        clearInterval(timer)
        resolve(document.querySelector(selector))
      }
    }, 40)
  })
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

  // 计算绝对定位坐标 (包含视口滚动)
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
      <span class="tour-pointer-emoji">${options.customEmoji || '👆'}</span>
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
 * 第一步：触发动画二 (手指导向 CPK 波动标签，无文字提示纯手指)
 */
function triggerStep1Animation2() {
  step1AnimState = 2
  removeClickPointer()

  const tipSpan = document.getElementById('tour-step1-action-text')
  if (tipSpan) {
    tipSpan.innerText = '动效指引：请点击上方「CPK波动」标签切换视图'
  }

  setTimeout(() => {
    const cpkTab = document.querySelector('#tour-tab-cpk')
    if (!cpkTab) return

    // 为 CPK 波动标签增加呼吸高亮
    cpkTab.classList.add('tour-highlight-pulse')

    const handleCpkTabClick = () => {
      // 移除呼吸动效与手指
      cpkTab.classList.remove('tour-highlight-pulse')
      removeClickPointer()

      if (tipSpan) {
        tipSpan.innerText = '✓ 已切换 CPK 波动，即将进入下一步...'
      }

      if (onUserInteractCallback) {
        onUserInteractCallback('switch-to-cpk')
      }

      // 停顿 2 秒后自动流转进入第二步
      clearTimeout(autoAdvanceTimer)
      autoAdvanceTimer = setTimeout(() => {
        if (activeDriver && typeof activeDriver.moveNext === 'function') {
          activeDriver.moveNext()
        }
      }, 2000)
    }

    // 绑定 tab 元素点击
    cpkTab.addEventListener('click', handleCpkTabClick, { once: true })

    // 挂载纯手指指示器 (不显示文字标签)
    renderClickPointer(cpkTab, '', {
      topPercent: 1.0,
      leftPercent: 0.5,
      offsetY: 6,
      onClick: handleCpkTabClick
    })
  }, 250)
}

/**
 * 第二步：触发动画二 (手指导向推荐参数按钮，无文字提示纯手指)
 */
function triggerStep2Animation2() {
  step2AnimState = 2
  removeClickPointer()

  const tipSpan = document.getElementById('tour-step2-action-text')
  if (tipSpan) {
    tipSpan.innerText = '动效指引：请点击该行的「查看推荐」按钮调取工艺参数'
  }

  setTimeout(() => {
    const recBtn = document.querySelector('#tour-spec-action-table .tour-recommend-btn') ||
                   document.querySelector('#tour-spec-action-table .action-btn')
    if (recBtn) {
      // 保持推荐参数按钮呼吸动效
      recBtn.classList.add('tour-highlight-pulse')

      const handleRecBtnClick = () => {
        recBtn.classList.remove('tour-highlight-pulse')
        removeClickPointer()

        if (onUserInteractCallback) {
          onUserInteractCallback('open-recommend-dialog')
        }

        // 关键：等待推荐参数弹窗在 DOM 中完全展开后，才将聚光灯推进到弹窗 (第三步)
        waitForDialogReady('.rec-param-dialog').then(() => {
          setTimeout(() => {
            if (activeDriver && typeof activeDriver.moveNext === 'function') {
              activeDriver.moveNext()
            }
          }, 250)
        })
      }

      recBtn.addEventListener('click', handleRecBtnClick, { once: true })

      // 挂载纯手指指示器 (不显示文字标签)
      renderClickPointer(recBtn, '', {
        topPercent: 1.0,
        leftPercent: 0.5,
        offsetY: 6,
        onClick: handleRecBtnClick
      })
    }
  }, 350)
}

/**
 * 看板交互式新手引导全新 5 步业务流程闭环定义
 */
export const tourSteps = [
  // 步骤 1: 监测整体趋势，锁定异常日期
  {
    element: '#tour-cpk-trend',
    popover: {
      title: '📈 第一步：监测整体合格率趋势，锁定异常日期',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>柱状图颜色分布</strong>：不同颜色代表各工段（TU/TG/TB/复合）异常率占比，鼠标悬浮可查看具体指标与异常胎数。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>折线与预警点</strong>：折线代表日环比增幅，虚线上方的红圈/高点代表异常率上升，点击柱形图即可锁定日期并展开排查。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">👆</span>
          <span id="tour-step1-action-text">动效指引：请点击图中的异常柱形图，进入当日深度排查</span>
        </div>
      `,
      side: 'bottom',
      align: 'center'
    }
  },
  // 步骤 2: 定位核心规格，查看机台源头和解决方案
  {
    element: '#tour-spec-action-table',
    popover: {
      title: '📋 第二步：定位核心规格，查看机台源头和解决方案',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>紧急程度排序</strong>：依据预警球颜色与负向贡献度降序排列（🔴红色高优恶化 > 🟠橙色中度预警 > 🟡黄色关注）。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>点击行动措施</strong>：直指主要责任机台，点击行动措施按钮可一键调取算法推荐的最佳工艺参数。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">👆</span>
          <span id="tour-step2-action-text">动效指引：请点击选定预警规格，联动右侧工序并查看推荐参数</span>
        </div>
      `,
      side: 'right',
      align: 'start'
    }
  },
  // 步骤 3: 聚光灯聚焦参数推荐窗口
  {
    element: '.rec-param-dialog',
    popover: {
      title: '⚙️ 第三步：查看专属轻量工艺参数推荐',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>工艺参数推荐</strong>：系统对比历史海量生产数据与同型标杆机台，智能计算出该机台的最优设定值与公差区间。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>落地闭环改善</strong>：工艺员可依据推荐值下发机台微调，消除异常波动。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">👆</span>
          <span>动效指引：请点击弹窗右上角关闭按钮，返回查看全链路流转状态</span>
        </div>
      `,
      side: 'bottom',
      align: 'center'
    }
  },
  // 步骤 4: 关闭后聚光灯聚焦工序图
  {
    element: '#tour-process-sankey',
    popover: {
      title: '🔄 第四步：查看该规格的生产状态',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>全链路工序展示</strong>：透视该规格在「成型 ➔ 硫化 ➔ 检测」工序链路的实际物料流转路径与分流占比。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>瓶颈机台透视</strong>：流转图中带红色发光光晕的节点即为主要质量瓶颈机台，直观定位工段短板。</div>
          </div>
        </div>
        <div class="tour-action-tip">
          <span class="tour-action-tip-icon">👉</span>
          <span>请点击「下一步」，查看物料批次质量追溯</span>
        </div>
      `,
      side: 'left',
      align: 'start'
    }
  },
  // 步骤 5: 聚光灯聚焦物料追溯展示
  {
    element: '#tour-lot-tracking',
    popover: {
      title: '📦 第五步：物料批次追溯分析',
      description: `
        <div class="tour-point-list">
          <div class="tour-point-item">
            <span class="tour-point-num">1</span>
            <div class="tour-point-text"><strong>物料批次质量追溯</strong>：展示选定规格所使用胶料、帘布等原材料批次的 CPK 控制区间与实测波动。</div>
          </div>
          <div class="tour-point-item">
            <span class="tour-point-num">2</span>
            <div class="tour-point-text"><strong>全链路闭环达成</strong>：已完整掌握从「整体趋势 ➔ 核心规格 ➔ 参数推荐 ➔ 工艺流转 ➔ 物料追溯」的诊断全流程！</div>
          </div>
        </div>
      `,
      side: 'top',
      align: 'center'
    }
  }
]

export function useDashboardTour() {
  /**
   * 平滑推进到下一步
   */
  const nextStep = () => {
    removeClickPointer()
    clearTimeout(autoAdvanceTimer)
    document.querySelectorAll('.tour-highlight-pulse').forEach(el => el.classList.remove('tour-highlight-pulse'))
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
    clearTimeout(autoAdvanceTimer)
    document.querySelectorAll('.tour-highlight-pulse').forEach(el => el.classList.remove('tour-highlight-pulse'))

    const stepIndex = state?.activeIndex ?? -1

    if (stepIndex === 0) {
      step1AnimState = 1
      // 步骤 1: 整体合格率趋势与锁定异常日期
      setTimeout(() => {
        const chartWrap = document.querySelector('#tour-cpk-trend .chart-body-container') ||
                          document.querySelector('#tour-cpk-trend .production-anomaly-chart-wrap') ||
                          document.querySelector('#tour-cpk-trend .card-body')

        if (chartWrap) {
          // 动画效果一：手指引导用户点击选中柱形图
          renderClickPointer(chartWrap, '点击异常柱形图', {
            topPercent: 0.65,
            leftPercent: 0.42,
            offsetY: 6,
            onClick: () => {
              if (onUserInteractCallback) {
                onUserInteractCallback('select-anomaly-date')
              }
              triggerStep1Animation2()
            }
          })
        }
      }, 400)
    } else if (stepIndex === 1) {
      step2AnimState = 1
      // 步骤 2: 定位核心规格，查看机台源头和解决方案 (全程聚焦在表格)
      setTimeout(() => {
        const firstSpecTd = document.querySelector('#tour-spec-action-table .el-table__body-wrapper tbody tr:first-child td:first-child') ||
                            document.querySelector('#tour-spec-action-table .clickable-row td:first-child') ||
                            document.querySelector('#tour-spec-action-table .col-spec-code')

        if (firstSpecTd) {
          // 动画效果一：引导用户点击核心规格
          renderClickPointer(firstSpecTd, '点击选中核心规格', {
            topPercent: 1.0,
            leftPercent: 0.5,
            offsetY: 8,
            onClick: () => {
              firstSpecTd.click()
              if (onUserInteractCallback) {
                onUserInteractCallback('select-spec-row')
              }
              triggerStep2Animation2()
            }
          })
        }
      }, 450)
    } else if (stepIndex === 2) {
      // 步骤 3: 聚光灯聚焦参数推荐窗口
      setTimeout(() => {
        const closeBtn = document.querySelector('.rec-param-dialog .el-dialog__headerbtn')
        if (closeBtn) {
          renderClickPointer(closeBtn, '点击关闭弹窗', {
            topPercent: 1.0,
            leftPercent: 0.5,
            offsetY: 8,
            onClick: () => {
              closeBtn.click()
            }
          })
        }
      }, 350)
    } else if (stepIndex === 3) {
      // 步骤 4: 关闭后聚光灯聚焦工序图
      setTimeout(() => {
        const sankeyEl = document.querySelector('#tour-process-sankey')
        if (sankeyEl) {
          sankeyEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 150)
    } else if (stepIndex === 4) {
      // 步骤 5: 聚光灯聚焦物料追溯展示
      setTimeout(() => {
        const lotEl = document.querySelector('#tour-lot-tracking')
        if (lotEl) {
          lotEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 150)
    }
  }

  /**
   * 启动新手漫游引导 (严格规则：仅在用户主动点击顶栏新手引导时 force = true 启动)
   * @param {boolean} force 是否强制唤起
   * @param {Function} onAction 用户交互代理回调
   */
  const startTour = async (force = false, onAction = null) => {
    if (onAction) {
      onUserInteractCallback = onAction
    }

    // 仅在用户主动点击顶栏新手引导按钮时触发
    if (!force) {
      return
    }

    // 重置步骤微状态
    step1AnimState = 1
    step2AnimState = 1

    // 点击后自动切换到 Yield 不良这个部分开始展示
    if (onUserInteractCallback) {
      onUserInteractCallback('start-tour')
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
        clearTimeout(autoAdvanceTimer)
        document.querySelectorAll('.tour-highlight-pulse').forEach(el => el.classList.remove('tour-highlight-pulse'))
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
   * @param {number} expectedStepIndex 当前步骤索引
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
    registerTourHandler,
    notifyTourDateSelected,
    notifyTourSpecSelected,
    tourSteps
  }
}
