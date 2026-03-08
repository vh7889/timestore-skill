---
name: timestore-rush
description: 使用统一配置文件执行 TimeStore 自动化任务：查询可买秒数、查询账户余额、查询充币地址、查询市场 KOL 列表、单次先查后买、达到目标金额后全仓卖出、按阈值抢购、开盘后抢购、暴力抢购，并在关键结果后发送飞书通知。用户提到 TimeStore 抢购、查询 estimateVolume、查询 USDT 余额、查询充币地址、查询市场发行人/KOL、单次直买、达到预期卖出全部、等待开盘、批量并发下单、飞书提醒时使用此技能。
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

## 单次直买（先查后买）

执行命令：

```bash
python scripts/buy_once_by_max.py --config config/config.toml
```

流程说明：

- 先调用 `maxBuy` 查询当前 `amount` 可买秒数。
- 再将返回的 `estimateVolume` 和 `amount` 一起作为参数调用 `confirmBuy`。
- 单次顺序执行，不使用并发、不使用最长运行时长循环。
- 最终会把 `confirmBuy` 结果发送到飞书（成功/失败都会发）。

## 达到预期卖出全部

执行命令：

```bash
python scripts/sell_all_when_target.py --config config/config.toml
```

配置参数（`config/config.toml`）：

- `issuer_id`：卖出目标发行人 ID
- `auth_token`：TimeStore Bearer Token
- `feishu_url`：卖出结果通知 Webhook
- `sell_min_accept_amount`：触发全卖的最低金额阈值（`amount >= 该值`）
- `sell_check_interval_seconds`：轮询 `maxSell` 的间隔秒数
- `verify_ssl`：是否校验 SSL 证书（默认 `false`）

流程说明：

- 先调用 `position/info` 获取当前 `availableVolume`（可卖秒数）。
- 循环调用 `maxSell`，监控当前可卖金额 `amount`。
- 当 `amount >= sell_min_accept_amount` 时，调用 `confirmSell`，按当前 `availableVolume` 全部卖出。
- 成功卖出后结束，并将结果推送到飞书。

可选参数：

- `--config`：配置文件路径（默认 `config/config.toml`）
- `--target-amount`：覆盖配置里的 `sell_min_accept_amount`
- `--check-interval`：覆盖配置里的 `sell_check_interval_seconds`
- `--raw`：打印本次关键接口原始返回

## 执行说明

- 为保持与旧脚本一致，建议默认 `verify_ssl=false`。
- `rush` 模式在首次下单成功后停止。
- `bruteforce` 模式即使成功也会继续请求，直到超时。
- 任一模式下单成功后会发送飞书通知。

## 日志保存

- 所有脚本每次运行都会自动创建日志文件。
- 日志目录：`timestore-skill/logs/`
- 文件命名：`脚本名-YYYYMMDD-HHMMSS.log`
- 终端输出和日志文件会同时保留（实时写入）。

## 查询持仓秒数

执行命令：

```bash
python scripts/query_position_volume.py --config config/config.toml
```

输出规则：

- 输出 `availableVolume`（可用秒数）
- 输出 `holdVolume`（总持仓秒数）

可选参数：

- `--raw`：打印完整接口返回

## 指定秒数卖出（先查后卖）

执行命令：

```bash
python scripts/sell_by_volume_once.py --config config/config.toml --volume 100
```

流程说明：

- 先调用 `maxSell` 查询指定 `volume` 可卖金额 `amount`
- 再将 `volume` 和该 `amount` 作为参数调用 `confirmSell`
- 单次顺序执行，不走并发循环
- 最终将卖出结果发送到飞书

可选参数：

- `--raw`：打印完整接口返回
