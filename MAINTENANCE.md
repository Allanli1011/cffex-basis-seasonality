# 🔧 运维交接手册 (MAINTENANCE.md)

## 📌 项目名称
**中金所基差日历效应分析系统 (cffex-basis-seasonality)**

## 👨‍💼 负责人
- **开发**：表哥 (Data)
- **运维**：小曼 (Ops)

## 🚀 核心任务
每日收盘后（17:15），自动更新 **16个主力合约** 的最新数据，并生成 **日历效应对比图**。

## 🛠️ 操作指南

### 1. 每日自动运行 (Cron)
请配置以下 Cron 任务：
- **时间**：`15 17 * * *` (每天 17:15)
- **命令**：
  ```bash
  python3 /Users/kumamon/.openclaw/workspace/agents/data/projects/cffex-basis-seasonality/scripts/02_current_analysis.py
  ```
- **功能**：
  - 自动检测是否为交易日（非交易日自动休眠）。
  - 增量抓取当天 IF/IH/IC/IM 主力合约数据。
  - 更新 SQLite 数据库 (`data/cffex_basis.db`)。
  - 生成 16 张图表到 `output/` 目录。

### 2. 输出文件位置
- **图表路径**：`projects/cffex-basis-seasonality/output/`
- **文件名格式**：`basis_IF2609.png`, `basis_IM2603.png` 等。

### 3. 常见问题排查 (FAQ)
**Q: 为什么今天没有生成报告？**
A: 检查日志，如果显示 `😴 今天不是交易日`，说明是正常的节假日休眠。

**Q: 图表里的红线断了或者没有最新点？**
A: 可能是中金所数据源延迟。可以尝试手动运行一次脚本（见下文）。

**Q: 数据库损坏怎么办？**
A: 运行 `scripts/01_load_history_robust.py`，它会重新从 2019年 开始全量抓取并修复数据库（耗时约 20 分钟）。

### 4. 手动补录数据
如果某天漏跑了，或者想强制更新：
```bash
# 强制运行增量更新 (会自动补齐当天数据)
python3 scripts/02_current_analysis.py
```

---
**致小曼：**
这套系统已经配置了 **全量历史数据库** (2019-2026)，非常稳健。你只需要监控每天 17:15 的 Cron 任务是否成功即可。如果遇到报错，直接找表哥。😎
