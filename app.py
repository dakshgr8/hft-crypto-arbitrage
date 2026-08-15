import os
import sys
import time
import asyncio
import signal
import multiprocessing
from aiohttp import web

from config import PAIRS_CONFIG, LOG_CSV_PATH, LOG_TO_CSV, TELEMETRY_INTERVAL_SEC, IPC_SHARED_MEMORY_NAME, MAX_QUOTE_AGE_DELTA_MS
from logger import ArbitrageLogger
from engine import ArbitrageEngine
from watchdog import ConnectionWatchdog, TimestampNormalizer, PTPSyncValidator
from ipc_manager import SharedMemoryIPCManager
from telemetry_agent import OutOfBandTelemetryAgent

from phase3_scanner import isolated_exchange_worker, evaluation_loop, telemetry_loop

# Global references for cleanup and web endpoints
GLOBAL_ENGINE = None
GLOBAL_LOGGER = None
GLOBAL_IPC = None
GLOBAL_WORKERS = []
GLOBAL_WATCHDOG = None

HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HFT Crypto Arbitrage — Live Cloud Monitor</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0a0e17;
            --bg-card: #111827;
            --bg-card-hover: #1f2937;
            --border: #1f293d;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --green: #10b981;
            --green-glow: rgba(16, 185, 129, 0.2);
            --red: #ef4444;
            --accent: #3b82f6;
            --yellow: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            padding: 24px;
            line-height: 1.5;
        }
        .container { max-width: 1300px; margin: 0 auto; }
        
        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }
        .header-title { display: flex; align-items: center; gap: 12px; }
        .pulse-dot {
            width: 12px;
            height: 12px;
            background: var(--green);
            border-radius: 50%;
            box-shadow: 0 0 12px var(--green);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }
        h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; }
        .tag {
            font-size: 0.75rem;
            background: rgba(59, 130, 246, 0.15);
            color: var(--accent);
            padding: 4px 10px;
            border-radius: 9999px;
            font-weight: 600;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }
        .header-actions { display: flex; gap: 10px; align-items: center; }
        .btn {
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .btn:hover { background: var(--bg-card-hover); border-color: var(--accent); }
        .btn-primary { background: var(--accent); color: white; border: none; }
        .btn-primary:hover { background: #2563eb; }

        /* KPI Cards Grid */
        .grid-kpi {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            transition: transform 0.2s, border-color 0.2s;
        }
        .card:hover { border-color: #374151; }
        .card-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }
        .card-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem;
            font-weight: 700;
        }
        .card-sub {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 4px;
        }
        .text-green { color: var(--green); }
        .text-red { color: var(--red); }
        .text-accent { color: var(--accent); }
        .text-yellow { color: var(--yellow); }

        /* Sections */
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Tables & Orderbooks */
        .grid-two {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }
        @media (max-width: 900px) {
            .grid-two { grid-template-columns: 1fr; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            font-family: 'JetBrains Mono', monospace;
        }
        th, td {
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            background: rgba(0,0,0,0.2);
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        tr:hover td { background: var(--bg-card-hover); }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-green { background: rgba(16, 185, 129, 0.15); color: var(--green); }
        .badge-yellow { background: rgba(245, 158, 11, 0.15); color: var(--yellow); }
        .badge-blue { background: rgba(59, 130, 246, 0.15); color: var(--accent); }

        footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">
                <div class="pulse-dot"></div>
                <h1>HFT Crypto Arbitrage Cloud Engine</h1>
                <span class="tag">Render 24/7 WebService</span>
            </div>
            <div class="header-actions">
                <span id="last-updated" class="card-sub" style="margin-right: 8px;">Syncing...</span>
                <a href="/api/report" target="_blank" class="btn">📄 Markdown Report</a>
                <a href="/api/download-csv" class="btn btn-primary">⬇️ Download CSV Ledger</a>
            </div>
        </header>

        <!-- KPI Summary Cards -->
        <div class="grid-kpi">
            <div class="card">
                <div class="card-label">Cumulative Net Return</div>
                <div id="cum-pnl" class="card-value text-green">+$0.0000</div>
                <div id="cum-roi" class="card-sub">Paper ROI: +0.00%</div>
            </div>
            <div class="card">
                <div class="card-label">Paper Portfolio Balance</div>
                <div id="paper-balance" class="card-value">$21,000.00</div>
                <div class="card-sub">Starting: $21,000.00 USDT</div>
            </div>
            <div class="card">
                <div class="card-label">Trades & Win Rate</div>
                <div id="trades-win" class="card-value text-accent">0 (100%)</div>
                <div id="total-vol" class="card-sub">Volume: $0.00 USDT</div>
            </div>
            <div class="card">
                <div class="card-label">Evaluation Latency</div>
                <div id="avg-latency" class="card-value">0.00 µs</div>
                <div id="matrix-scans" class="card-sub">0 matrix scans</div>
            </div>
            <div class="card">
                <div class="card-label">Circuit Breaker Status</div>
                <div id="circuit-status" class="card-value text-green" style="font-size: 1.1rem;">OPTIMAL</div>
                <div class="card-sub">Layer-0 Drawdown Protection</div>
            </div>
        </div>

        <!-- Live Orderbook Quotes & Latency Profiler -->
        <div class="grid-two">
            <div class="card">
                <div class="section-title">
                    <span>📡 Live L2 Orderbooks (Shared Memory)</span>
                    <span class="badge badge-green">Real-Time</span>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Asset</th>
                                <th>Exchange</th>
                                <th>Ask (Buy)</th>
                                <th>Bid (Sell)</th>
                                <th>Spread</th>
                            </tr>
                        </thead>
                        <tbody id="orderbooks-body">
                            <tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Streaming live orderbooks...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="section-title">
                    <span>⏱️ Venue Latency Profiler ($p_{99}$)</span>
                    <span class="badge badge-blue">Microsecond Shield</span>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Exchange</th>
                                <th>p50 RTT</th>
                                <th>p99 RTT</th>
                                <th>Routing Status</th>
                            </tr>
                        </thead>
                        <tbody id="latency-body">
                            <tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Profiling network latency...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Recent Paper Trades Ledger -->
        <div class="card">
            <div class="section-title">
                <span>📜 Recent Executed Paper Trades</span>
                <span class="badge badge-blue">Auto-Updating</span>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Trade ID</th>
                            <th>Time (UTC)</th>
                            <th>Asset</th>
                            <th>Buy Venue @ Price</th>
                            <th>Sell Venue @ Price</th>
                            <th>Size</th>
                            <th>Net Profit</th>
                            <th>Cum. Balance</th>
                        </tr>
                    </thead>
                    <tbody id="trades-body">
                        <tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No arbitrage trades recorded yet. Scanning orderbooks...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <footer>
            <p>HFT Crypto Arbitrage Daemon &bull; Running Headless on Render WebService &bull; 6 Venues (Binance, Bybit, OKX, Kraken, Coinbase, Gate.io)</p>
        </footer>
    </div>

    <script>
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                if (!res.ok) return;
                const data = await res.json();
                
                // Update KPI Cards
                const pnl = data.paper_tracker.cumulative_pnl || 0;
                const pnlEl = document.getElementById('cum-pnl');
                pnlEl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(4) + ' USDT';
                pnlEl.className = 'card-value ' + (pnl >= 0 ? 'text-green' : 'text-red');
                
                const roi = data.paper_tracker.roi_pct || 0;
                document.getElementById('cum-roi').textContent = 'Paper ROI: ' + (roi >= 0 ? '+' : '') + roi.toFixed(3) + '%';
                document.getElementById('paper-balance').textContent = '$' + (data.paper_tracker.current_balance || 21000).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                
                const totalTrades = data.paper_tracker.total_trades || 0;
                const winRate = data.paper_tracker.win_rate || 100;
                document.getElementById('trades-win').textContent = totalTrades + ' (' + winRate.toFixed(1) + '%)';
                document.getElementById('total-vol').textContent = 'Volume: $' + (data.paper_tracker.total_volume || 0).toLocaleString('en-US', {minimumFractionDigits: 2});
                
                document.getElementById('avg-latency').textContent = (data.engine.avg_lat || 0).toFixed(2) + ' µs';
                document.getElementById('matrix-scans').textContent = (data.engine.count || 0).toLocaleString() + ' matrix scans';
                
                const circuit = data.circuit_breaker.circuit_status || 'OPTIMAL';
                const circuitEl = document.getElementById('circuit-status');
                circuitEl.textContent = circuit;
                circuitEl.className = 'card-value ' + (circuit.includes('OPTIMAL') ? 'text-green' : 'text-yellow');

                document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();

                // Render Orderbooks
                if (data.orderbooks && Object.keys(data.orderbooks).length > 0) {
                    let obRows = '';
                    for (const [asset, venues] of Object.entries(data.orderbooks)) {
                        for (const [ex, book] of Object.entries(venues)) {
                            if (book.ask > 0 && book.bid > 0) {
                                const spread = (book.ask - book.bid).toFixed(2);
                                obRows += `<tr>
                                    <td><strong>${asset}</strong></td>
                                    <td><span class="badge badge-blue">${ex.toUpperCase()}</span></td>
                                    <td class="text-red">$${book.ask.toFixed(2)}</td>
                                    <td class="text-green">$${book.bid.toFixed(2)}</td>
                                    <td>$${spread}</td>
                                </tr>`;
                            }
                        }
                    }
                    if (obRows) document.getElementById('orderbooks-body').innerHTML = obRows;
                }

                // Render Latency Profiler
                if (data.latency_profiles && data.latency_profiles.venue_profiles) {
                    let latRows = '';
                    for (const [ex, prof] of Object.entries(data.latency_profiles.venue_profiles)) {
                        latRows += `<tr>
                            <td><strong>${ex.toUpperCase()}</strong></td>
                            <td>${prof.p50.toFixed(1)} ms</td>
                            <td>${prof.p99.toFixed(1)} ms</td>
                            <td><span class="badge ${prof.status.includes('OPTIMAL') ? 'badge-green' : 'badge-yellow'}">${prof.status}</span></td>
                        </tr>`;
                    }
                    document.getElementById('latency-body').innerHTML = latRows;
                }

                // Render Recent Trades
                if (data.paper_tracker.recent_trades && data.paper_tracker.recent_trades.length > 0) {
                    let trRows = '';
                    const trades = [...data.paper_tracker.recent_trades].reverse();
                    for (const t of trades) {
                        trRows += `<tr>
                            <td><code>${t.trade_id}</code></td>
                            <td>${t.timestamp}</td>
                            <td><strong>${t.asset}</strong></td>
                            <td>${t.buy_ex} @ $${t.buy_price.toFixed(2)}</td>
                            <td>${t.sell_ex} @ $${t.sell_price.toFixed(2)}</td>
                            <td>${t.quantity.toFixed(4)}</td>
                            <td class="text-green">+$${t.net_profit.toFixed(4)}</td>
                            <td>$${t.balance.toFixed(2)}</td>
                        </tr>`;
                    }
                    document.getElementById('trades-body').innerHTML = trRows;
                }
            } catch (err) {
                console.error("Failed to refresh stats:", err);
            }
        }

        fetchStats();
        setInterval(fetchStats, 3000); // 3-second live auto-refresh
    </script>
</body>
</html>
"""

async def handle_dashboard(request):
    return web.Response(text=HTML_DASHBOARD_TEMPLATE, content_type='text/html')

async def handle_health(request):
    return web.json_response({
        "status": "healthy",
        "service": "hft-crypto-arbitrage",
        "timestamp": time.time(),
        "active_workers": len([w for w in GLOBAL_WORKERS if w.is_alive()])
    })

async def handle_stats(request):
    global GLOBAL_ENGINE, GLOBAL_LOGGER
    if not GLOBAL_ENGINE or not GLOBAL_LOGGER:
        return web.json_response({"status": "initializing"})
        
    engine_stats = GLOBAL_ENGINE.get_telemetry_snapshot() or {}
    
    roi_pct = ((GLOBAL_LOGGER.current_balance - GLOBAL_LOGGER.initial_capital) / GLOBAL_LOGGER.initial_capital) * 100.0 if GLOBAL_LOGGER.initial_capital > 0 else 0.0
    win_rate = (GLOBAL_LOGGER.winning_trades / GLOBAL_LOGGER.total_trades * 100.0) if GLOBAL_LOGGER.total_trades > 0 else 100.0
    
    payload = {
        "engine": {
            "count": engine_stats.get('count', 0),
            "opp_count": engine_stats.get('opp_count', 0),
            "avg_lat": engine_stats.get('avg_lat', 0.0),
            "ghost_rejected": engine_stats.get('ghost_rejected', 0),
            "cross_region_skipped": engine_stats.get('cross_region_skipped', 0),
        },
        "paper_tracker": {
            "initial_capital": GLOBAL_LOGGER.initial_capital,
            "current_balance": GLOBAL_LOGGER.current_balance,
            "cumulative_pnl": GLOBAL_LOGGER.cumulative_pnl,
            "roi_pct": roi_pct,
            "total_trades": GLOBAL_LOGGER.total_trades,
            "winning_trades": GLOBAL_LOGGER.winning_trades,
            "win_rate": win_rate,
            "total_volume": GLOBAL_LOGGER.total_volume,
            "total_fees": GLOBAL_LOGGER.total_fees,
            "recent_trades": GLOBAL_LOGGER.recent_trades
        },
        "circuit_breaker": engine_stats.get('circuit_breaker', {}),
        "latency_profiles": engine_stats.get('latency_profiles', {}),
        "orderbooks": engine_stats.get('books', {})
    }
    return web.json_response(payload)

async def handle_report(request):
    global GLOBAL_LOGGER
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(base_dir, "PAPER_RETURNS_REPORT.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/markdown')
    return web.Response(text="# Report Initializing...", content_type='text/markdown')

async def handle_download_csv(request):
    global GLOBAL_LOGGER
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "paper_trading_ledger.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding='utf-8') as f:
            return web.Response(
                text=f.read(),
                content_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename="paper_trading_ledger.csv"'}
            )
    return web.Response(text="trade_id,timestamp_utc,asset,buy_exchange,buy_price,sell_exchange,sell_price,quantity,notional_usd,gross_spread_per_unit,gross_profit_usd,total_fees_usd,net_profit_usd,cumulative_net_pnl_usd,paper_balance_usd,eval_latency_micros\n", content_type='text/csv')

async def start_background_arbitrage():
    global GLOBAL_ENGINE, GLOBAL_LOGGER, GLOBAL_IPC, GLOBAL_WORKERS, GLOBAL_WATCHDOG
    
    print("\n[🚀 RENDER CLOUD ENGINE] Initializing Multi-Process Arbitrage Core...")
    
    GLOBAL_IPC = SharedMemoryIPCManager(create=True, shm_name=IPC_SHARED_MEMORY_NAME)
    telemetry_agent = OutOfBandTelemetryAgent()

    exchanges = ['binance', 'kraken', 'coinbase', 'bybit', 'okx', 'gateio']
    GLOBAL_WORKERS = []

    for ex in exchanges:
        p = multiprocessing.Process(
            target=isolated_exchange_worker,
            args=(ex, IPC_SHARED_MEMORY_NAME),
            name=f"Worker-{ex.upper()}"
        )
        p.daemon = True
        p.start()
        GLOBAL_WORKERS.append(p)
        print(f" [🔥 WORKER SPAWNED] {ex.upper()} (PID: {p.pid})")

    GLOBAL_LOGGER = ArbitrageLogger(LOG_CSV_PATH, enabled=LOG_TO_CSV)
    GLOBAL_WATCHDOG = ConnectionWatchdog()
    
    GLOBAL_ENGINE = ArbitrageEngine(logger=GLOBAL_LOGGER, use_ipc=True)
    GLOBAL_ENGINE.watchdog = GLOBAL_WATCHDOG

    asyncio.create_task(evaluation_loop(GLOBAL_ENGINE, interval_sec=0.01))
    asyncio.create_task(telemetry_loop(GLOBAL_ENGINE, GLOBAL_WATCHDOG, GLOBAL_WORKERS, telemetry_agent))
    print("[✅ CORE ONLINE] Evaluation & Telemetry loops active!\n")

async def on_startup(app):
    await start_background_arbitrage()

async def on_cleanup(app):
    global GLOBAL_IPC, GLOBAL_WORKERS
    print("\n[🛑 SHUTDOWN] Stopping worker processes and cleaning shared memory...")
    for p in GLOBAL_WORKERS:
        if p.is_alive():
            p.terminate()
            p.join(timeout=1.0)
    if GLOBAL_IPC:
        GLOBAL_IPC.close(unlink=True)
    print("[✨ CLEANUP COMPLETE]")

def create_app():
    app = web.Application()
    app.router.add_get('/', handle_dashboard)
    app.router.add_get('/health', handle_health)
    app.router.add_get('/api/stats', handle_stats)
    app.router.add_get('/api/report', handle_report)
    app.router.add_get('/api/download-csv', handle_download_csv)
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app

if __name__ == '__main__':
    multiprocessing.set_start_method('fork', force=True)
    port = int(os.environ.get("PORT", 10000))
    host = "0.0.0.0"
    print(f"==========================================================================")
    print(f" 🌐 STARTING HFT ARBITRAGE WEB SERVICE ON http://{host}:{port}")
    print(f"==========================================================================")
    
    app = create_app()
    web.run_app(app, host=host, port=port)
