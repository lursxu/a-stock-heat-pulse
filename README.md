# A-Stock Heat Pulse (A股热度脉冲监控系统)

全A股综合热度监控系统，结合交易数据与舆情数据，使用 Z-Score 异常检测算法实时发现热度快速拉升的股票，并通过飞书/钉钉推送告警。

## 功能

- 全A股实时扫描（5000+只），分钟级频率
- 综合热度 = 交易数据（量比、换手率、成交额）+ 舆情数据（东方财富股吧 + 雪球）
- 滑动窗口 + Z-Score 异常检测
- Web 管理面板：热度排行榜、趋势图、告警历史、系统配置
- 飞书/钉钉 Webhook 告警推送
- SQLite 存储，数据保留 3 个月

## 技术栈

- Backend: Python 3.10 + FastAPI + APScheduler + akshare
- Frontend: Vue3 + Vite + ECharts
- Database: SQLite

## 快速开始

```bash
# 安装后端依赖
cd backend && pip install -r requirements.txt

# 安装前端依赖并构建
cd frontend && npm install && npm run build

# 启动服务
cd backend && python main.py
```

访问 http://localhost:8000 即可使用。

## 配置

编辑 `backend/config.yaml` 修改扫描间隔、告警阈值、Webhook URL 等参数，也可通过 Web 管理面板在线修改。
