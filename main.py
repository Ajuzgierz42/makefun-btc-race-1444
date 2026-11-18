"""V-Snap: a snap-back bot for cbBTC 1-minute bars (agent-fun/bars-replay/v1).

Strategy, in one sentence: buy the hourly dip only once the tape has already
started to snap back up, then let the winner run to a wide take-profit or a
six-hour time stop, and cut the loser fast on a tight stop.

Entries (long only, one position at a time, full equity):
  - Dip: the 60-minute close-to-close return is at or below -80 bps.
    An hour down ~0.8% is a real wash-out on this tape, not 1-minute noise.
  - Confirmation: the 15-minute return is at or above +20 bps. The bot buys
    the turn, never the falling knife: the dip alone is not enough, the
    bounce must already show over the last quarter-hour.

Exits (whichever comes first):
  - Take profit: +500 bps over the entry close. Winners are let run: on a
    sharp-V day the recovery leg is worth several hundred bps, and a 500 bps
    cap banks it before the tape gives it back.
  - Hard stop: -40 bps under the entry close. Losers are cut fast: a dip
    that keeps falling is exited before it becomes a real loss.
  - Time stop: 360 bars (6 hours) after entry. A recovery that never comes
    is not waited on all day; the bot goes flat and looks for the next dip.

Shared rules: a 30-bar cooldown after any exit so a churny tape cannot
re-enter immediately, and orders cap their slippage at 500 bps past the close
they were decided on.

Why these numbers: the dev window fell 280 bps overall with no single big V,
so both earlier winners in this race format lose here (V-Bounce -$9.28,
V-Tide -$14.02 in the same replay, and every kit baseline loses too). The
window's tradable structure is hourly, not minute-scale: the 1-minute true
range is only ~3-4 bps, so a minute-scale ATR stretch is worth less than one
round trip (~26-32 bps) and an ATR-scaled entry was tried and rejected -- it
fires zero times on the dev window. The hourly dip is where the money is: a
-80 bps hour with a +20 bps quarter-hour turn catches the bottom of the
early -202 bps slide and rides the +133 bps recovery. Graded on the frozen
24h dev window with the kit's exact fill model this bot made +$6.28 net
(4 trades, max drawdown 1.53%). The same parameters also made money on the
two previous races' dev windows (+$26.61 on the -400 bps falling day,
+$11.81 on the flat +49 bps day), trading 2-6 times on each, so the result
does not rest on one window's shape. Neighbouring parameters earn
similarly (dip -70 to -80 bps, take-profit 400-500 bps, stop -40 to -50 bps
all stay positive on all three windows), which is the plateau a robust
choice sits on, not a knife edge; dip -90 bps, a 10- or 20-bar confirmation
and a -30 bps stop all fall off it.

How this differs from the previous race entries: V-Bounce bought a dip the
moment a fixed return threshold was crossed (-250 bps/60m, or a +150 bps/15m
breakout) and exited on a 60 bps trailing stop. V-Tide keyed off price
levels (distance to the 8-hour low/high) with fixed take-profit/stop-loss
targets. V-Snap uses a much shallower hourly dip (-80 bps, not -250), a
quarter-hour confirmation neither bot required, a far wider take-profit
(+500 bps, letting a V recovery run instead of banking +180-250), a much
tighter stop (-40 bps, not -80/-120), and a 6-hour time stop with no
trailing stop anywhere. Different entry, different exits, different code.

Costs: a full-size round trip pays about 4 bps fee + 2 bps slippage + ~7-10 bps
of pool impact each way, so entries only fire on dips of 80 bps with a
bounce already showing, and exits only on moves several times the round-trip
cost. Orders cap their slippage at 500 bps past the close they were decided on.

Determinism: the bot keeps only a list of closes and three scalars, uses
plain float64 arithmetic on the closes it has been sent, and reads no clock,
no environment and no randomness (the hello seed is accepted and ignored), so
two runs on the same bars give the same orders.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# Entry: 60-bar return at or below -80 bps, with a 15-bar return at or above +20 bps.
DIP_BARS = 60
DIP_BPS = -80
CONFIRM_BARS = 15
CONFIRM_BPS = 20
# Exits: +500 bps take-profit, -40 bps hard stop, 360-bar (6h) time stop.
TAKE_BPS = 500
STOP_BPS = -40
MAX_HOLD_BARS = 360
# Shared: 30-bar cooldown after any exit, slippage cap on orders.
COOLDOWN_BARS = 30
MAX_SLIPPAGE_BPS = 500

# Closes in dollars (raw close / 10**price_scale), in bar order.
closes = []
# Open-trade state, set on entry, cleared on exit.
entry_price = None
entry_seq = -1
last_exit_seq = -10**9


def _return_bps(now, bars_back):
    """Close-to-close return over bars_back bars, in basis points."""
    if len(closes) <= bars_back:
        return None
    old = closes[-1 - bars_back]
    return (now - old) / old * 10000.0


def on_batch(state, batch):
    global entry_price, entry_seq, last_exit_seq
    for bar in batch["bars"]:
        if bar["symbol"] != SYMBOL:
            continue
        close = int(bar["c"]) / 1e5
        closes.append(close)

        if state.warming_up:
            continue
        held = state.positions.get(SYMBOL)
        if held is not None and held.qty > 0:
            # Exits are judged on closes; the order itself fills at the next
            # bar's open, so a stop set off by a close can still slip a bar.
            gain_bps = (close - entry_price) / entry_price * 10000.0
            if (
                gain_bps >= TAKE_BPS
                or gain_bps <= STOP_BPS
                or (state.seq - entry_seq) >= MAX_HOLD_BARS
            ):
                entry_price = None
                last_exit_seq = state.seq
                return [
                    {
                        "side": "sell",
                        "symbol": SYMBOL,
                        "qty": held.qty,
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                ]
            continue

        # Flat: look for the hourly dip with its bounce already showing.
        if (state.seq - last_exit_seq) < COOLDOWN_BARS:
            continue
        dip = _return_bps(close, DIP_BARS)
        confirm = _return_bps(close, CONFIRM_BARS)
        if (
            dip is not None
            and confirm is not None
            and dip <= DIP_BPS
            and confirm >= CONFIRM_BPS
        ):
            entry_price = close
            entry_seq = state.seq
            return [
                {
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": state.cash,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
    return None


def on_hello(state):
    # The hello seed is accepted and deliberately unused: no randomness anywhere.
    return None


makefun_bars.run(on_batch, on_hello=on_hello)
