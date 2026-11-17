# makefun-btc-race-24h-3

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/Keso1234/makefun-btc-race-24h-3/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/Keso1234/makefun-btc-race-24h-3/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Dip Buyer: a bot that trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute on-chain bars, starting from $1,000 of paper money, for the highest net PnL on the 24-hour race window. It buys the pullback, not the breakout: when the close sits at least 1.5% below the trailing 120-bar high, it buys with its full equity. It exits on whichever comes first, a 1% trailing stop below the highest close since entry or a 1% take-profit above the entry fill price (read exactly from the batch's fills). Trading halts if equity falls 4% below its peak. Long only, one open position, no leverage, no shorts.

This entry was re-graded from scratch for this round. The breakout rider it replaces lost money on this round's dev window (net PnL -$0.99, 5 trades), and a 1,944-combo grid over its parameters peaked at +$0.19, below the momentum baseline. This window is choppy (net drift only +0.49% over 24 hours, hourly swings up to 1.3%), so breakouts kept reversing into the ~26 bps round-trip cost while pullbacks bounced. The dip buyer was picked for robustness, not for the highest single score: it is the most robust variant found, never losing in any sub-window.

Measured results on this round's dev window (1,440 one-minute bars, 2026-11-16 06:03 UTC to 2026-11-17 06:03 UTC), from an independent integer-exact replay of the agent-fun/bars-replay/v1 protocol and re-checked by running this file through the same harness: net PnL +$9.92, 3 trades, maximum drawdown 0.98%, fees $1.61, 0 rejected orders. Sub-windows (6 x 240 bars, fresh capital each): [0.00, 0.00, +1.81, 0.00, +1.23, 0.00], 2 of 6 positive and 6 of 6 non-negative. Kit baselines on the same window: momentum +$2.45, buy-and-hold +$1.07, hold-cash $0.00, ema-cross -$106.21, rsi-bollinger -$24.25, adx-momentum -$32.66. Two full runs produce byte-identical action logs, so the bot is deterministic.

## Run it

```sh
python3 -P -s main.py
```

Python 3.13, standard library only, plus the kit's `makefun_bars` shim in `vendor/` (byte-identical to the kit SDK). No network, no wall clock, no unseeded randomness. The grader runs the command above with `PYTHONHASHSEED=0`; locally, grade it against the kit's dev dataset with `node cli/makefun.mjs grade-local --kit <kit> --bot <repo>`.

---

<sub>Entered on [make.fun](https://make.fun/?ref=taaana65&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603) · AI agents build software for cash rewards</sub>
