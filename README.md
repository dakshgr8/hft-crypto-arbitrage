# ⚡ Phase 2 Institutional Crypto Arbitrage & Resilience Platform

An ultra-fast, multi-exchange crypto arbitrage scanning, resilience, and execution platform engineered for sub-microsecond price evaluation, state consistency validation, VWAP slippage protection, capital rebalancing, and chaos survival.

## 🏛️ Supported Exchanges (6 Active WebSocket Streams)

1. **Binance** (Spot `bookTicker`)
2. **Kraken** (Spot Ticker)
3. **Coinbase** (Spot Ticker)
4. **Bybit** (V5 Spot Ticker)
5. **OKX** (V5 Spot Ticker)
6. **Gate.io** (V4 Spot Ticker)

---

## 📂 System Architecture & Phase 2 Modules

```text
/home/daksh/arbitrage/
├── config.py                 # Multi-pair symbol mapping, fee rates, drift & chaos thresholds
├── engine.py                 # Microsecond matrix evaluation + Phase 2 state validation
├── inventory_manager.py      # Capital Efficiency Score (CES) & Inventory Auto-Rebalance Manager
├── watchdog.py               # Sequence validator, Quote Age Drift Filter (Ghost Spread Detector) & Heartbeat Watchdog
├── chaos_simulator.py        # Chaos execution simulator (Packet drops, Partial fills & Emergency Flattener)
├── depth_engine.py           # Level 2 Orderbook VWAP & Slippage Calculator ($1k, $5k, $10k)
├── triangular_engine.py      # Single-exchange 3-pair loop cycle finder (USDT->BTC->ETH->USDT)
├── logger.py                 # Async non-blocking CSV opportunity logger
├── scanner.py                # Main Phase 2 entry point & telemetry dashboard
├── requirements.txt          # Package dependencies
├── paper_trades.json         # Simulated trades & balance history
└── exchanges/                # WebSocket connectors per exchange
    ├── binance.py | kraken.py | coinbase.py | bybit.py | okx.py | gateio.py
```

---

## 🛡️ Phase 2 Resilience Features Overview

### 1. State Consistency & Ghost Arbitrage Protection (`watchdog.py`)
- **Sequence Number Validation (`SequenceValidator`)**: Verifies packet sequence continuity (`new_seq == last_seq + 1`). Drops corrupted or out-of-order packets.
- **Quote Timestamp Drift Filter (`TimestampSyncValidator`)**: Compares exchange server timestamps ($|t_A - t_B|$). Rejects time-warped spreads exceeding `MAX_QUOTE_AGE_DELTA_MS` (500ms).
- **Connection Heartbeat Watchdog (`ConnectionWatchdog`)**: Identifies idle WebSocket connections (> 5s) and triggers automatic reconnection.

### 2. Inventory Manager & Capital Efficiency Score (`inventory_manager.py`)
- Tracks real-time USDT/crypto distribution across all 6 exchanges.
- Calculates **Capital Efficiency Score (CES %)** to measure portfolio distribution health.
- Identifies starving exchanges (< 10% USDT ratio) and emits automated cross-chain rebalance alerts.

### 3. Chaos Execution Simulator & Emergency Flattener (`chaos_simulator.py`)
- Injects real-world market chaos:
  - **5% WebSocket Packet Loss**
  - **10% Partial Fill Ratios**
  - **5% Leg B Execution Rejection ("Hanging Delta")**
- **Emergency Market Flattener**: Immediately liquidates unhedged inventory at market price if Leg B fails, neutralizing directional exposure.

---

## 🚀 How to Run Phase 2 System

```bash
/home/daksh/arbitrage_env/bin/python3 /home/daksh/arbitrage/scanner.py
```
