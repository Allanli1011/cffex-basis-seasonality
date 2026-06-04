# CFFEX 基差日历效应分析 (cffex-basis-seasonality)

## 📌 项目目标
分析中金所股指期货合约的**基差日历效应**（Seasonality），通过对比历史上所有同月合约（如历年9月合约）的基差走势，判断当前合约（如 IF2609）是否存在异常偏离。

## 📊 核心指标
1. **基差率**：(期货价格 - 现货指数) / 现货指数 * 100%
   - *注*：使用百分比而非绝对点数，因为指数从3000点涨到5000点，基差绝对值不可比。
   - *年化*：绘图默认按距到期自然日年化（基差率 × 365 / 剩余自然日），使数值具备"年化贴水 / 套利收益率"的金融含义；临近到期年化发散，截断剩余 < 3 自然日的点。
2. **上市天数**：合约上市首日记为第1天，以此对齐所有年份的时间轴。
3. **历史区间**：
   - **中位数/均值**：基差率的历史常态。
   - **波动范围**：历史最大值与最小值的包络线（蓝色阴影）。

## 🛠️ 技术栈
- **Python 3.12+**
- **Pandas** (时间序列对齐)
- **Matplotlib/Seaborn** (绘图)
- **AkShare** (历史数据源)

## 📂 目录结构
```
cffex-basis-seasonality/
├── README.md
├── data/cffex_basis.db            # SQLite 缓存（期货日线 + 现货 + 基差/基差率）
├── scripts/
│   ├── common.py                  # 共享：配置 / 取数 / 基差&年化计算 / 绘图
│   ├── 00_init_db.py              # 初始化数据库
│   ├── 01_load_history_robust.py  # 全量历史回填（按交易日抓 CFFEX 日汇总）
│   ├── 02_current_analysis.py     # 每日增量更新 + 出图（cron 主链路）
│   ├── 03_migrate_basis_rate.py   # 一次性迁移：补 basis_rate 列 / 修 BLOB
│   └── plot_basis.py              # 按 --product/--month 出图 CLI
└── output/                        # 图表输出（basis_*.png + 联系表）
```

## 🚀 运行方式
```bash
# 首次：初始化并全量回填历史（默认 2019 至今）
python3 scripts/00_init_db.py
python3 scripts/01_load_history_robust.py

# 每日：增量更新 + 出图（cron 主链路）
python3 scripts/02_current_analysis.py
python3 scripts/02_current_analysis.py --date 20260213   # 补录指定历史交易日

# 按需出图（指定品种 / 月份，从数据库读）
python3 scripts/plot_basis.py --product IF --month 09
python3 scripts/plot_basis.py --all                      # 数据库中全部合约
```
*(参数说明：--product 指定品种 IF/IH/IC/IM，--month 指定目标合约月份)*

## 📅 更新日志
- **2026-06-04**: 结构重构 (P1)——抽出 `common.py` 收编共享逻辑，删除 8 个废弃/调试脚本；脚本全面 argparse 化（`--date` 补录、`plot_basis --product/--month`）；`except: pass` 改 `logging` 记日志，增量更新加现货/期货同日校验。
- **2026-06-04**: 绘图口径升级为**年化基差率 (%)**——按距到期自然日年化（基差率 × 365 / 剩余自然日，到期日 = 合约月第三个周五）；临近到期（剩余 < 3 自然日）截断以规避年化发散。年化为绘图层派生，不额外占用数据库存储。
- **2026-06-04**: 数据口径修正 (P0)——基差统一为**基差率 (%)**：新增 `basis_rate` 列并回填全部历史数据；修复每日增量任务将 `volume`/`hold` 误写为二进制 BLOB 的问题；所有图表纵轴改为基差率 (%)。迁移脚本见 `scripts/03_migrate_basis_rate.py`。
- **2026-02-15**: 项目立项，验证历史数据获取能力。
