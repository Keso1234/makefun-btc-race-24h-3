"""Dip Buyer -- btc-race-24h-20261117-0603 ("Race a BTC trading bot live
for 24 hours", $250, top 10 paid).

Strategy: buy the pullback, not the breakout. On each 1-minute cbBTC/USDC
bar the bot watches the trailing 120-bar high. When the close sits at
least 150 bps (1.5%) below that high, it buys with its full equity
(100% of equity, long only, one open position). It exits on whichever
comes first: a 100 bps trailing stop below the highest close seen since
entry, or a 100 bps take-profit above the entry fill price (read exactly
from the batch's fills, never estimated). Trading halts for the rest of
the window if equity falls 400 bps below its peak. Orders fill at the
next bar's open with max_slippage_bps 100.

Why this, and not the breakout rider it replaces: the reference
Confirmed Breakout Rider was re-graded from scratch on THIS round's dev
window (1,440 bars, 2026-11-16 06:03 UTC to 2026-11-17 06:03 UTC) with an
independent integer-exact replay of agent-fun/bars-replay/v1 and lost
money: net PnL -$0.99, 5 trades, max drawdown 0.78%. A 1,944-combo grid
over the rider's parameters (breakout lookback, momentum window and
threshold, EMA length, size, trailing stop, warmup) could do no better
than +$0.19, and its best extended variant (+$1.78, one trade) never
trades in any 240-bar sub-window and stays below the momentum baseline.
This window is choppy (net drift only +0.49%, hourly swings to +-1.3%):
breakouts keep reversing into the 26 bps round-trip cost. Pullbacks
bounce instead: in the same grid 65% of 864 dip-buyer combos were
profitable and 361 beat the best baseline.

Measured results on this round's dev window (independent replay, and
re-checked by running this file as a subprocess through the same
harness): net PnL +$9.92, 3 trades, max drawdown 0.98%, fees $1.61,
0 rejected orders. Sub-windows (6 x 240 bars, fresh capital each):
[0.00, 0.00, +1.81, 0.00, +1.23, 0.00] -- 2 of 6 positive, 6 of 6
non-negative, worst 0.00. No candidate in either grid won more
sub-windows, so this is the most robust variant found, not the
highest-PnL one (the highest, +$24.54, loses -$2.08 in one sub-window).
Kit baselines on the same window: momentum +$2.45, buy-and-hold +$1.07,
hold-cash $0.00, ema-cross -$106.21, rsi-bollinger -$24.25,
adx-momentum -$32.66. Determinism: two full runs produce byte-identical
action logs (sha256 089db152420d04a1f6b5da62314717a8f4ac18b7527a25b80398c378fee7bc41).

Python 3.13, standard library only (plus the kit's makefun_bars shim in
vendor/, byte-identical to the kit SDK). Deterministic: no clock, no
unseeded randomness, no network, no files outside the repository.
Run: python3 -P -s main.py (the grader's fixed command).
"""
# NOTE: the string literal below is the reference rider's original module
# docstring, kept verbatim (it now opens a fresh string literal of its
# own). The Dip Buyer docstring above is this entry's module docstring.
"""Confirmed Breakout Rider for make.fun btc-race-24h-20261115-0828.

Trades cbBTC/USDC on 1-minute bars, long only, $1,000 paper money.
Protocol agent-fun/bars-replay/v1 via the vendored kit shim.

Strategy (trend-following breakout, deliberately NOT dip-buying: the
previous race's dip-buying Washout Rebound bot passed its dev window
at +$10.87 and then lost -$105.89 live, so this bot only buys strength
that is already confirmed, in small size, and exits fast):
  Entry: the close breaks above its 45-bar high AND the 15-minute
    return exceeds +0.5% AND the close sits above its 60-bar EMA.
    All three must agree, so the bot stays out of choppy and falling
    markets and only joins a move that is already running. Size is
    50% of cash, one position at a time.
  Exit: a 0.5% trailing stop from the highest close since entry, a
    1.5% hard stop from the entry close, or a 240-bar max hold,
    whichever comes first; then a 60-bar cooldown before re-entry.
  Drawdown guard: if equity ever falls 4% below its running peak,
    flatten and stop trading for the rest of the window.
  Late insurance: if nothing has traded by bar 1200, take the next
    15-minute jump over 0.4% at 25% size (same exits); if still
    nothing by bar 1400, buy 25% once, so the entry meets the race
    guardrail of at least one trade even in a dead-flat window.
  Late cutoff: no fresh main entry in the last 30 bars (bar 1410 on),
    when no trend leg has time to develop before the final flatten
    and a new buy would pay the round-trip cost for a coin flip.

On the frozen dev window (BTC -4.0% over the day) the protocol-level
replay of this exact code gives +$13.38 net PnL with 3 round trips
(6 trades), max drawdown 0.47%; the screening backtest was positive
on 5 of 6 fresh-capital sub-windows and non-negative on all 6, and
every kit baseline lost money on the same window (best baseline
momentum24 -$40.92, ema-cross -$134.94). The dev gate needs > $0.

Every decision is a pure function of the closes seen so far plus the
account state, so two runs on the same bars produce byte-identical
orders. Standard library only, no clock, no network, no files
outside the repository.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

# --- Strategy parameters (screened on the dev window, kept round) ---
WARMUP_BARS = 120        # bars of history needed before any entry
HI_WINDOW = 45           # breakout lookback: close above this high
MOM_WINDOW = 15          # momentum window in minutes
MOM_THRESHOLD = 0.005    # entry needs a 15-min return over +0.5%
EMA_BARS = 60            # trend filter length
SIZE = 0.5               # fraction of cash per entry
TRAIL = 0.005            # trailing stop from peak close
HARD_STOP = 0.015        # hard stop from the entry close
MAX_HOLD = 240           # max bars held
COOLDOWN = 60            # bars to wait after an exit before re-entry
DD_HALT = 0.04           # halt trading if equity falls 4% below peak
LATE_BAR = 1200          # late insurance: no trade yet by this bar
LATE_JUMP = 0.004        # late insurance: 15-min jump over 0.4%
LATE_SIZE = 0.25         # late insurance size
FORCE_BAR = 1400         # last resort: buy once if still no trade
ENTRY_CUTOFF = 1410      # no fresh main/late-jump entry at this bar or later
MAX_SLIPPAGE_BPS = 100   # cap vs the latest close (1-min moves are ~12 bps sd)
MIN_NOTIONAL = 1000000   # $1 in quote units (protocol minimum)


class Bot:
    def __init__(self):
        self.symbol = None
        self.closes = []          # closes seen so far, in USD (floats)
        self.ema = None           # 60-bar EMA of closes
        self.holding = False      # a position is open
        self.peak_px = None       # highest close since the position opened
        self.entry_close = None   # close of the bar the buy was decided on
        self.bars_held = 0        # bars since the position opened
        self.cool_until = -1      # bar index before which no new entry
        self.ever_traded = False  # any buy decision sent so far
        self.halted = False       # drawdown guard tripped
        self.peak_equity = None   # running peak equity in quote units

    def on_hello(self, state):
        self.symbol = state.hello["symbols"][0]["symbol"]
        self.peak_equity = state.equity

    def on_batch(self, state, batch):
        bar = state.latest.get(self.symbol)
        if bar is None:
            return []  # no bar for our symbol this minute: stay silent
        close = int(bar["c"]) / 10 ** state.symbols[self.symbol]["price_scale"]
        self.closes.append(close)
        n = len(self.closes) - 1  # index of this bar
        if self.ema is None:
            self.ema = close
        else:
            k = 2.0 / (EMA_BARS + 1)
            self.ema = close * k + self.ema * (1.0 - k)

        # Drawdown guard on real account equity.
        if self.peak_equity is None:
            self.peak_equity = state.equity
        elif state.equity > self.peak_equity:
            self.peak_equity = state.equity
        if not self.halted and state.equity < self.peak_equity * (1.0 - DD_HALT):
            self.halted = True
        holding = state.positions.get(self.symbol)
        if holding is not None and holding.qty > 0:
            self.ever_traded = True
            if self.halted:
                return self._sell(state, holding)
            if self.peak_px is None:
                self.peak_px = close
            elif close > self.peak_px:
                self.peak_px = close
            self.bars_held += 1
            if (close <= self.peak_px * (1.0 - TRAIL)
                    or close <= self.entry_close * (1.0 - HARD_STOP)
                    or self.bars_held >= MAX_HOLD):
                self.holding = False
                self.cool_until = n + COOLDOWN
                return self._sell(state, holding)
            return []

        # Flat: clear trade state, then look for an entry.
        self.holding = False
        self.peak_px = None
        self.entry_close = None
        self.bars_held = 0
        if self.halted or state.warming_up:
            return []
        if n <= WARMUP_BARS:
            return []
        if n < self.cool_until:
            return []

        # Main entry: confirmed breakout (not in the last 30 bars).
        hi = max(self.closes[n - HI_WINDOW:n])
        ret15 = close / self.closes[n - MOM_WINDOW] - 1.0
        if n < ENTRY_CUTOFF and close > hi and ret15 > MOM_THRESHOLD and close > self.ema:
            return self._buy(state, SIZE, close)

        # Late insurance: no trade yet, take the next decent jump.
        if not self.ever_traded and LATE_BAR < n < ENTRY_CUTOFF and ret15 > LATE_JUMP:
            return self._buy(state, LATE_SIZE, close)

        # Last resort: still no trade very late, buy once at small size.
        if not self.ever_traded and n >= FORCE_BAR:
            return self._buy(state, LATE_SIZE, close)
        return []

    def _buy(self, state, fraction, close):
        notional = int(state.cash * fraction)
        if notional < MIN_NOTIONAL:
            return []
        self.holding = True
        self.entry_close = close
        self.peak_px = close
        self.bars_held = 0
        self.ever_traded = True
        return [{"side": "buy", "symbol": self.symbol,
                 "notional_quote_units": notional,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]

    def _sell(self, state, holding):
        return [{"side": "sell", "symbol": self.symbol,
                 "qty": holding.qty, "max_slippage_bps": MAX_SLIPPAGE_BPS}]


# ---------------------------------------------------------------------------
# Dip Buyer (this round's strategy, added in this session).
#
# Re-grade note: the Breakout Rider class below was re-graded on this
# round's dev window and lost -$0.99 (5 trades); a 1,944-combo grid over
# its parameters peaked at +$0.19, and its best extended variant (+$1.78)
# never trades in any 240-bar sub-window. The rider is therefore NOT run:
# main() below rebinds the bot's on_batch/on_hello to the dip functions
# defined here before calling the shim's run(). The rider code stays in
# the file as the reference it was adapted from, but it is dead code in
# this entry -- only _dip_on_batch / _dip_on_hello ever execute.
#
# Dip parameters (chosen from the grid + robustness scan, not from the
# single best full-window score):
#   DIP_LOOKBACK  120 bars for the trailing high -- a 1-hour-plus anchor,
#                 so the "high" is a real swing high, not minute noise.
#   DIP_BPS       150 bps below that high -- deep enough that the
#                 pullback is a genuine dip (shallower dips, 50-80 bps,
#                 kept catching falling knives in down sub-windows).
#   DIP_SIZE_BPS  10000 -- full equity. The edge is a few big swings, so
#                 half size halves the gain while the costs stay per
#                 round trip; 50% size scored +$5.58 at best vs +$9.92.
#   DIP_TRAIL_BPS 100 bps trailing stop on closes -- tight enough to
#                 bank the bounce before chop gives it back.
#   DIP_TP_BPS    100 bps take-profit above the entry FILL price -- the
#                 bounce target; the fill price is read exactly from the
#                 batch's fills, never estimated from a close.
#   DIP_HALT_BPS  400 bps equity drawdown halt, as in the rider.
# Entry needs no momentum or EMA confirmation: on this window the
# confirmation filters only delayed entries into worse fills.
# ---------------------------------------------------------------------------

DIP_LOOKBACK = 120
DIP_BPS = 150
DIP_SIZE_BPS = 10000
DIP_TRAIL_BPS = 100
DIP_TP_BPS = 100
DIP_HALT_BPS = 400
DIP_SLIPPAGE_BPS = 100

# Dip state, kept in module globals so the two callbacks share it. All of
# it is reset in _dip_on_hello, which the shim calls once per execution
# before the first batch.
_dip_symbol = "CBBTC"
_dip_closes = []
_dip_highs = []
_dip_peak_close = None
_dip_entry_price = None
_dip_peak_equity = None
_dip_halted = False


def _dip_on_hello(state):
    """Reset dip state and take the traded symbol from hello."""
    global _dip_symbol, _dip_closes, _dip_highs
    global _dip_peak_close, _dip_entry_price, _dip_peak_equity, _dip_halted
    _dip_symbol = state.hello["symbols"][0]["symbol"]
    _dip_closes = []
    _dip_highs = []
    _dip_peak_close = None
    _dip_entry_price = None
    _dip_peak_equity = None
    _dip_halted = False


def _dip_on_batch(state, batch):
    """One batch: record fills, then decide at most one order.

    The protocol gives the bot exactly one reply per batch. A buy decided
    here fills at the next bar's open; its exact fill price arrives in the
    following batch's fills, and that price -- not any close -- is the
    take-profit reference. Exits sell the whole position.
    """
    global _dip_peak_close, _dip_entry_price, _dip_peak_equity, _dip_halted
    # Learn the entry fill price from the harness's own fills. A buy fill
    # sets it; a sell fill clears it (flat again).
    for fill in batch.get("fills", []):
        if fill.get("symbol") == _dip_symbol and fill.get("status") == "filled":
            if fill["side"] == "buy":
                _dip_entry_price = int(fill["price"])
            elif fill["side"] == "sell":
                _dip_entry_price = None
    close = state.close(_dip_symbol)
    if close is None:
        return []
    bar = state.latest[_dip_symbol]
    _dip_closes.append(close)
    _dip_highs.append(int(bar["h"]))
    if _dip_peak_equity is None or state.equity > _dip_peak_equity:
        _dip_peak_equity = state.equity
    if not _dip_halted and state.equity * 10000 < _dip_peak_equity * (10000 - DIP_HALT_BPS):
        _dip_halted = True
    holding = state.positions.get(_dip_symbol)
    if holding is not None and holding.qty > 0:
        if _dip_peak_close is None or close > _dip_peak_close:
            _dip_peak_close = close
        trail_hit = close * 10000 < _dip_peak_close * (10000 - DIP_TRAIL_BPS)
        tp_hit = (
            _dip_entry_price is not None
            and close * 10000 >= _dip_entry_price * (10000 + DIP_TP_BPS)
        )
        if trail_hit or tp_hit:
            _dip_peak_close = None
            _dip_entry_price = None
            return [{"side": "sell", "symbol": _dip_symbol, "qty": holding.qty,
                     "max_slippage_bps": DIP_SLIPPAGE_BPS}]
        return []
    _dip_peak_close = None
    _dip_entry_price = None
    if _dip_halted or state.warming_up:
        return []
    if len(_dip_closes) <= DIP_LOOKBACK:
        return []
    # The dip: close at least DIP_BPS below the trailing DIP_LOOKBACK-bar
    # high (previous bars only, never the current bar's own high).
    trail_high = max(_dip_highs[-DIP_LOOKBACK - 1:-1])
    if close * 10000 <= trail_high * (10000 - DIP_BPS):
        notional = state.equity * DIP_SIZE_BPS // 10000
        if notional < MIN_NOTIONAL:
            return []
        return [{"side": "buy", "symbol": _dip_symbol,
                 "notional_quote_units": notional,
                 "max_slippage_bps": DIP_SLIPPAGE_BPS}]
    return []


def main():
    bot = Bot()
    # Re-grade decision (this round): the rider bound here lost -$0.99 on
    # this round's dev window and no retune of it beat the momentum
    # baseline, while the dip buyer measured +$9.92 with 6/6 non-negative
    # sub-windows. Run the dip callbacks instead; the rider instance
    # above is constructed but never traded.
    bot.on_batch = _dip_on_batch
    bot.on_hello = _dip_on_hello
    makefun_bars.run(bot.on_batch, on_hello=bot.on_hello)


if __name__ == "__main__":
    main()
