---
name: timestore-rush
description: 使用统一配置文件执行 TimeStore 自动化任务：查询可买秒数、查询账户余额、查询充币地址、查询市场 KOL 列表、按阈值抢购、开盘后抢购、暴力抢购，并在成功后发送飞书通知。用户提到 TimeStore 抢购、查询 estimateVolume、查询 USDT 余额、查询充币地址、查询市场发行人/KOL、等待开盘、批量并发下单、飞书提醒时使用此技能。
---

# TimeStore 抢购技能

使用一个配置文件和一个脚本，替代原来的 4 个独立 Python 文件。

## 统一参数名

在 `config/config.toml` 中使用以下固定参数名：

- `auth_token`：TimeStore 的 Bearer Token
- `feishu_url`：飞书机器人 Webhook 地址
- `concurrency`：并发任务数
- `max_duration_seconds`：最长尝试时长（秒）
- `expect_volume`：最低可接受秒数（所有抢购模式都会使用）
- `amount`：下单金额（USDT）
- `issuer_id`：发行人 ID

可选参数：

- `verify_ssl`（默认 `false`）
- `open_check_interval_seconds`（默认 `0.2`）
- `market_type`（默认 `0`）

## 初始化步骤

1. 将 `config/config.example.toml` 复制为 `config/config.toml`（已提供同名模板时可直接修改）。
2. 填入真实的 `auth_token`、`feishu_url` 和策略参数。
3. 确保运行环境已安装 `aiohttp`。

## 运行模式

在技能目录 `timestore-skill` 下执行：

```bash
python scripts/timestore_runner.py --mode query --config config/config.toml
python scripts/timestore_runner.py --mode rush --config config/config.toml
python scripts/timestore_runner.py --mode rush_after_open --config config/config.toml
python scripts/timestore_runner.py --mode bruteforce --config config/config.toml
```

也可以使用独立脚本（更接近你原来的多版本习惯）：

```bash
python scripts/rush_threshold.py --config config/config.toml
python scripts/rush_after_open.py --config config/config.toml
python scripts/rush_bruteforce.py --config config/config.toml
```

如果要一次同时运行多个抢购模式：

```bash
python scripts/run_all_rush.py --config config/config.toml
```

可选只跑部分模式：

```bash
python scripts/run_all_rush.py --config config/config.toml --modes rush,bruteforce
```

与旧脚本对应关系：

- `query`：等价于 `查询能买多少秒数.py`
- `rush`：等价于 `抢购代码.py`（先查秒数，达到 `expect_volume` 阈值才下单）
- `rush_after_open`：等价于 `抢购代码2.py`（先等待开盘，再按 `expect_volume` 阈值抢购）
- `bruteforce`：等价于 `暴力抢购不结束版.py`（不查秒数，直接并发下单，`expect_volume` 作为下单参数传入）

## 查询余额

执行命令：

```bash
python scripts/query_balance.py --config config/config.toml
```

如需同时打印完整返回 JSON：

```bash
python scripts/query_balance.py --config config/config.toml --raw
```

输出规则：

- 按你的要求，从 `fundAccount.myBalanceList` 的第一个元素读取 `balanceValue` 作为余额输出。
- 默认输出格式：`balanceValue=3.18419`

## 查询充币地址

执行命令：

```bash
python scripts/query_deposit_address.py --config config/config.toml --coin USDT
```

可选参数：

- `--chain`：传 `mainChainName` 过滤值，不传时使用空字符串（与抓包一致）
- `--raw`：打印完整返回 JSON

输出规则：

- 重点读取并输出 `data.address` 作为充币地址。
- 同时输出 `coin` 和 `mainChainName` 便于核对链类型。

## 查询市场 KOL 列表

执行命令：

```bash
python scripts/query_market_kol.py --config config/config.toml
```

可选参数：

- `--type`：请求参数 `type`，默认空字符串（即 `type=`）
- `--raw`：打印完整返回 JSON

输出规则：

- 先输出总数量：`count=...`
- 再逐行输出关键字段：`id`、`issuerName`、`issuerStatus`、`issuerLastPrice`、`modeType`

## 执行说明

- 为保持与旧脚本一致，建议默认 `verify_ssl=false`。
- `rush` 模式在首次下单成功后停止。
- `bruteforce` 模式即使成功也会继续请求，直到超时。
- 任一模式下单成功后会发送飞书通知。
