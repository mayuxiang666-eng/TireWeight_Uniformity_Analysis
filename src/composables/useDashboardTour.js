import { nextTick } from 'vue'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import '../assets/tour.css'

const TOUR_STORAGE_KEY = 'has_seen_kanban_tour_v1'

/**
 * 看板交互式新手引导 5 步流程定义
 */
const tourSteps = [
  {
    element: '#tour-header-filters',
    popover: {
      title: '🎯 1. 全局指标与维度筛选',
      description: '在此处可自由切换全厂核心质量指标（RFPP CPK / RFH1 CPK / CONY / 胎重 Diff），并按时间维度与生产班组进行动态筛选。',
      side: 'bottom',
      align: 'start'
    }
  },
  {
    element: '#tour-cpk-trend',
    popover: {
      title: '📈 2. 整体 CPK 控制图与趋势联动',
      description: '实时呈现全厂加权综合 CPK 与 SPC 控制限波动。💡 核心操作：点击图表上的任意日期数据点，可驱动下方核心行动表与工序流转全屏联动分析！',
      side: 'bottom',
      align: 'center'
    }
  },
  {
    element: '#tour-spec-action-table',
    popover: {
      title: '📋 3. 核心规格行动表 (预警与负向贡献)',
      description: '系统严格依据 🔴/🟠/🟡 三级预警和负向拉低贡献降序排查恶化源头。悬浮可查看完整指标卡片，点击任意规格行即可在右侧流转图中深度聚焦。',
      side: 'right',
      align: 'start'
    }
  },
  {
    element: '#tour-process-sankey',
    popover: {
      title: '🔄 4. 生产工序流转与瓶颈机台诊断',
      description: '全景透视成型、硫化、检测链路的工艺分流。带红色阴影发光圈的节点即为瓶颈机台；还可切换查看 30 天「全量最佳路径」与「机台组合分析」。',
      side: 'left',
      align: 'start'
    }
  },
  {
    element: '#tour-help-trigger',
    popover: {
      title: '💡 5. 随时重温引导',
      description: '🎉 恭喜！你已掌握看板核心交互逻辑。日常使用中若需重新回顾，随时点击顶栏的「💡 新手引导」按钮即可再次启动。',
      side: 'bottom',
      align: 'end'
    }
  }
]

let activeDriver = null

export function useDashboardTour() {
  /**
   * 启动新手漫游引导
   * @param {boolean} force 是否强制唤起（如用户主动点击帮助按钮）
   */
  const startTour = async (force = false) => {
    if (!force) {
      const hasSeen = localStorage.getItem(TOUR_STORAGE_KEY)
      if (hasSeen === 'true') {
        return
      }
    }

    await nextTick()

    // 确保 DOM 已渲染且首个步骤元素存在
    const firstEl = document.querySelector('#tour-header-filters')
    if (!firstEl) {
      // 若元素尚未挂载完，延迟重试一次
      setTimeout(() => startTour(force), 400)
      return
    }

    if (activeDriver) {
      activeDriver.destroy()
    }

    activeDriver = driver({
      showProgress: true,
      animate: true,
      allowClose: true,
      overlayColor: '#0f172a',
      overlayOpacity: 0.72,
      stagePadding: 6,
      stageRadius: 10,
      popoverOffset: 12,
      nextBtnText: '下一步 →',
      prevBtnText: '← 上一步',
      doneBtnText: '完成探索 🎉',
      progressText: '{{current}} / {{total}}',
      onDestroyStarted: () => {
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
   * 重置已读状态（供测试或重新教学）
   */
  const resetTourState = () => {
    localStorage.removeItem(TOUR_STORAGE_KEY)
  }

  return {
    startTour,
    resetTourState,
    tourSteps
  }
}
