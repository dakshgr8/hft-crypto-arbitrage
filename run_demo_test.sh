#!/usr/bin/env bash
# ==============================================================================
# 🚀 Free Demo / Shadow Test Runner (Live Market Feed Scanner)
# Connects to real-time public L2 orderbooks across 6 exchanges with $0 cost.
# ==============================================================================

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="/home/daksh/arbitrage_env/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

echo "=========================================================================="
echo " 🌐 LAUNCHING HFT ARBITRAGE SCANNER (FREE SHADOW TEST MODE)"
echo " • Cost: \$0.00 (Public L2 WebSocket Streams)"
echo " • Exchanges: Binance, Bybit, OKX, Gate.io, Coinbase, Kraken"
echo " • Assets: BTC/USDT, ETH/USDT, SOL/USDT"
echo " • Mode: Real-time orderbook matrix scan & live telemetry dashboard"
echo "=========================================================================="
echo " Press [Ctrl+C] at any time to gracefully stop the scanner."
echo ""

exec "$PYTHON_BIN" phase3_scanner.py
