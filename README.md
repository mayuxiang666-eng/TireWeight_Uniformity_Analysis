# TireWeight_Uniformity_Analysis

轮胎重量与均匀性分析及 Cpk 诊断系统 (Tire Weight & Uniformity Analysis & Cpk Diagnostics System)

## 项目简介 (Project Overview)

本项目为轮胎生产质量数据分析与可视化诊断系统，核心用于轮胎重量 (Weight)、均匀性 (Uniformity, 如 RFV/LFV/CON 等) 及动态平衡性指标的监控、趋势分析、Cpk 工艺能力诊断与变异归因。

核心功能包括：
- **监控面板与指标卡片 (Dashboard)**：汇总全厂/工段/规格级别的产出、合格率、Cpk、规格异常数与警示指标。
- **全流程变异流向 (Sankey Diagram)**：可视化分析成型机、硫化机、均匀性检测机到成品指标的变异传播路径。
- **机器/工位 Cpk 聚类与对比 (Clustering & Heatmaps)**：基于 KMeans / GMM 算法对设备性能分布进行自动化分组与下钻对比。
- **组合下钻与归因树 (Attribution Tree)**：树状下钻分解设备组合 (如 CT+VULC+TU) 对关键指标偏差的影响。
- **自动智能诊断与建议 (Insights & Recommendations)**：基于统计学算法自动生成质量诊断报告与工艺调整建议。

---

## 技术栈 (Tech Stack)

- **前端 (Frontend)**: Vue 3, Vite, Element Plus, ECharts, Vue-ECharts, Pinia, Axios
- **后端 (Backend)**: Python, FastAPI / Flask, DuckDB, Pandas, Scikit-learn, NumPy
- **架构文档 (Docs)**: 详见 `docs/` 目录下的系统 Blueprint 与架构说明文档

---

## 快速启动 (Quick Start)

### 1. 前端运行 (Frontend)

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 生产环境构建
npm run build
```

### 2. 后端运行 (Backend)

```bash
cd backend

# 安装 Python 依赖
pip install -r requirements.txt

# 启动 FastAPI 服务
python run_server.py
```

---

## 项目结构 (Project Structure)

```
untitled1_v2/
├── backend/            # Python 数据分析与 API 服务
├── docs/               # 系统设计、控制点规范与诊断算法文档
├── src/                # Vue 3 前端应用源码
│   ├── api/            # API 请求封装
│   ├── components/     # 可复用 UI 视图与图表组件
│   ├── stores/         # Pinia 状态管理
│   └── views/          # Dashboard 页面布局
├── index.html          # HTML 入口
├── package.json        # Node 依赖与脚本定义
└── vite.config.js      # Vite 构建配置
```
