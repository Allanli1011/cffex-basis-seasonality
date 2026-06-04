# 🔧 运维交接手册 (MAINTENANCE.md)

## 📌 项目名称
**中金所基差日历效应分析系统 (cffex-basis-seasonality)**

## 👨‍💼 负责人
- **开发**：表哥 (Data)
- **运维**：小曼 (Ops)

## 🚀 核心任务
每日收盘后（17:15），自动更新 **16个主力合约** 的最新数据，并生成 **日历效应对比图**。

## 🛠️ 操作指南

### 1. 每日自动运行（GitHub Actions，推荐）
仓库已内置定时任务 `.github/workflows/daily-update.yml`：
- **触发**：周一至周五 `09:15 UTC`（= 17:15 北京时间，收盘后），也可在仓库 **Actions** 页面手动触发（Run workflow）。
- **功能**：装依赖 → 运行 `scripts/02_current_analysis.py`（自动判断交易日 → 增量抓取 IF/IH/IC/IM → 更新 `data/cffex_basis.db` → 生成图表）→ 把更新后的 `data/`、`output/` 自动 commit & push 回仓库。
- **监控**：在 Actions 页面看每日运行是否成功。

> ⚠️ GitHub Actions runner 在境外，访问新浪 / 中金所数据源可能不稳定；若频繁失败，可改用下方本地 Cron。

### 1b. 每日自动运行（本地 Cron，备选）
- **时间**：`15 17 * * *`（每天 17:15）
- **命令**（替换为你的实际部署路径）：
  ```bash
  python3 /path/to/cffex-basis-seasonality/scripts/02_current_analysis.py
  ```

### 2. 输出文件位置
- **图表路径**：`projects/cffex-basis-seasonality/output/`
- **文件名格式**：`basis_IF2609.png`, `basis_IM2603.png` 等。

### 3. 常见问题排查 (FAQ)
**Q: 为什么今天没有生成报告？**
A: 检查日志，如果显示 `今天不是交易日，跳过。`，说明是正常的节假日休眠。

**Q: 图表里的红线断了或者没有最新点？**
A: 可能是中金所数据源延迟。可以尝试手动运行一次脚本（见下文）。

**Q: 数据库损坏怎么办？**
A: 运行 `scripts/01_load_history_robust.py`，它会重新从 2019年 开始全量抓取并修复数据库（耗时约 20 分钟）。

### 4. 手动补录数据
如果某天漏跑了，或者想强制更新：
```bash
# 强制运行增量更新 (会自动补齐当天数据)
python3 scripts/02_current_analysis.py

# 补录某个历史交易日 (例如漏跑了 2026-02-13)
python3 scripts/02_current_analysis.py --date 20260213
```

---
**致小曼：**
这套系统已经配置了 **全量历史数据库** (2019-2026)，非常稳健。日常只需在 GitHub 的 **Actions** 页面监控每天的运行是否成功即可。如果遇到报错，直接找表哥。😎
