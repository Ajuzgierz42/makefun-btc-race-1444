# V-Snap — cbBTC snap-back bot for make.fun `btc-race-24h-20261118-1444`

Long-only bot trading Coinbase Wrapped BTC (cbBTC) on 1-minute bars, $1,000 paper
start, for the make.fun 24-hour BTC trading race.

## Strategy

Buy the hourly dip once the tape has already started to snap back up, then let
the winner run and cut the loser fast:

- **Entry:** 60-minute return ≤ −80 bps **and** 15-minute return ≥ +20 bps
  (dip + confirmation — never the falling knife).
- **Exits:** take-profit +500 bps, hard stop −40 bps, or a 360-bar (6 h) time
  stop, whichever comes first. 30-bar cooldown after any exit.
- Full equity per entry, one position at a time, `max_slippage_bps` 500.
- Python 3.13, standard library only; the `vendor/makefun_bars.py` shim is the
  kit's SDK copied byte-for-byte. No network, no clock, no randomness —
  deterministic (seeded from nothing; the `hello` seed is accepted and ignored).

## Local dev grade (exact replay of the kit harness fill model)

| Window | Net PnL | Trades | Max DD |
|---|---|---|---|
| `btc-race-24h-20261118-1444` dev (this race) | **+$6.28** | 4 | 1.53% |
| `btc-race-24h-20261115-0828` dev | +$26.61 | 6 | — |
| `btc-race-24h-20261117-0603` dev | +$11.81 | 2 | — |

Same parameters are positive on all three known 24 h windows (worst +$6.28,
total +$44.70). For comparison, on this race's dev window buy-and-hold loses
−$31.63 and every kit baseline loses (EMA-cross −$148.17, momentum −$23.87,
RSI-Bollinger −$39.92, ADX-momentum −$75.57), as do both previous winning
entries in this race format (V-Bounce −$9.28, V-Tide −$14.02).

## Files

- `main.py` — the bot
- `vendor/makefun_bars.py` — kit SDK shim (vendored, byte-for-byte)
- `LICENSE` — MIT
- `.makefun/owner.json` — payout wallet claim file
