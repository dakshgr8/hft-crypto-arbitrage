# ⚡ Institutional High-Frequency Crypto Arbitrage Platform (Phase 7)

An ultra-low-latency, multi-exchange cryptocurrency spatial arbitrage engine built with POSIX lock-free shared memory (`/dev/shm`), process isolation, sub-millisecond evaluation, Layer-0 Multi-Tier Drawdown Kill-Switches, Mark-out Trade Toxicity Analytics, and 24/7 WebService Deployment.

---

## 🏛️ Supported Exchanges (6 Active WebSocket Streams)

1. **Binance** (Spot L2 `bookTicker`)
2. **Bybit** (V5 Spot L2 `orderbook.1`)
3. **OKX** (V5 Spot L2 `bbo-tbt`)
4. **Gate.io** (V4 Spot L2 `spot.book_ticker`)
5. **Coinbase** (Advanced Trade L2 Ticker)
6. **Kraken** (Spot L2 Ticker)

---

## 🚀 24/7 Cloud Deployment on Render (Web Service)

You can run this engine 24/7 in the cloud on **Render** (free tier) so you don't have to keep your laptop powered on:

### Option A: 1-Click Render Blueprint Deployment
1. Log in to [Render.com](https://dashboard.render.com).
2. Click **New +** $\rightarrow$ **Blueprint**.
3. Connect your private GitHub repository `https://github.com/dakshgr8/hft-crypto-arbitrage`.
4. Render will automatically detect `render.yaml`, build the Python environment, and start the web service!

### Option B: Manual Web Service Setup on Render
1. Click **New +** $\rightarrow$ **Web Service**.
2. Select your repository `dakshgr8/hft-crypto-arbitrage`.
3. Configure settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Health Check Path**: `/health`
   - **Plan**: `Free`
4. Click **Create Web Service**.

Once deployed, visit your Render URL (e.g., `https://hft-crypto-arbitrage.onrender.com`) to view the **Live Web Dashboard** with real-time paper returns, live orderbooks, latency profiler, and CSV downloads.

---

## 📊 Live Web Dashboard & API Endpoints

* **`/`** — Interactive Dark-Mode Institutional Web Dashboard with live auto-refresh.
* **`/health`** — Health check endpoint returning active worker status (200 OK).
* **`/api/stats`** — JSON payload of all live telemetry, PnL, and orderbook quotes.
* **`/api/report`** — Raw markdown view of `PAPER_RETURNS_REPORT.md`.
* **`/api/download-csv`** — Direct download of `paper_trading_ledger.csv`.

---

## 🧪 Local Free Shadow Testing

Run locally without cloud servers:

```bash
cd /home/daksh/crypto-arbitrage
./run_demo_test.sh
```

### 📄 Real-Time Paper Tracking Documents
* **`PAPER_RETURNS_REPORT.md`**: Executive markdown report tracking cumulative paper ROI %, win rate, total volume, and asset breakdown.
* **`paper_trading_ledger.csv`**: Granular transaction ledger recording every paper trade execution with prices, quantities, fees, and PnL.

---

## 🛡️ Core Hard Capital Controls & Architecture

* **Process Isolation & POSIX Shared Memory**: Zero GIL contention; each exchange worker updates `/dev/shm` in isolation.
* **Seqlock Protocol**: Lock-free atomic reads with automatic "Stuck-Odd" write state sanitization upon worker restarts.
* **Multi-Tier Kill-Switch (`circuit_breaker.py`)**:
  * *Tier 1 (Soft Pause)*: 3 consecutive partial fills $\rightarrow$ 60-second cooldown.
  * *Tier 2 (Hard Neutralize)*: Daily drawdown $\le -1.5\%$ $\rightarrow$ Read-Only mode.
  * *Tier 3 (Emergency Lockdown)*: Multi-venue disconnect $\rightarrow$ Memory core dump.
* **Mark-Out Trade Toxicity ($M_{\Delta t}$)**: Evaluates trade profitability at $t+100\text{ms}$, $t+1\text{s}$, $t+10\text{s}$ against the Volume-Weighted Global Composite consensus ($P_{\text{composite}}$).
* **Latency Profiler (`latency_profiler.py`)**: Dynamic routing with 50% capital throttling at $>120\text{ms}$ and venue bypass at $>180\text{ms}$ $p_{99}$ RTT.
* **Perpetual Futures Hedger (`futures_hedger.py`)**: Delta-neutral hedging ($\Delta = 0$) with Post-Only "Chase the Book" maker protocol and Flash-Crash Taker fallback.
