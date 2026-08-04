import os

# Multi-Crypto Pair Symbol Mappings per Exchange
PAIRS_CONFIG = {
    'BTC': {
        'binance': 'btcusdt',
        'kraken': 'XBT/USDT',
        'coinbase': 'BTC-USDT',
        'bybit': 'BTCUSDT',
        'okx': 'BTC-USDT',
        'gateio': 'BTC_USDT'
    },
    'ETH': {
        'binance': 'ethusdt',
        'kraken': 'ETH/USDT',
        'coinbase': 'ETH-USDT',
        'bybit': 'ETHUSDT',
        'okx': 'ETH-USDT',
        'gateio': 'ETH_USDT'
    },
    'SOL': {
        'binance': 'solusdt',
        'kraken': 'SOL/USDT',
        'coinbase': 'SOL-USDT',
        'bybit': 'SOLUSDT',
        'okx': 'SOL-USDT',
        'gateio': 'SOL_USDT'
    }
}

# --- Phase 4 Regional Co-Location Clustering ---
# Overcomes optical speed-of-light delay (~150ms between Tokyo and Virginia).
# Deterministic sub-35ms HFT arbitrage only executes within the same physical geographic cluster.
REGIONAL_CLUSTERS = {
    'ap-northeast-1': {
        'name': 'Tokyo (APAC IT Hub)',
        'exchanges': ['binance', 'bybit', 'okx', 'gateio'],
        'avg_co_location_ping_ms': 1.8
    },
    'us-east-1': {
        'name': 'Northern Virginia (US East Hub)',
        'exchanges': ['coinbase', 'kraken'],
        'avg_co_location_ping_ms': 1.4
    }
}

# --- Phase 4 Exchange Rate Limit & Token Bucket Weight Settings ---
# Prevents HTTP 429 and HTTP 418 (IP Auto-Ban) during massive volatility spikes
API_RATE_LIMITS = {
    'binance':  {'max_weight_per_min': 2400, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'bybit':    {'max_weight_per_min': 2000, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'okx':      {'max_weight_per_min': 1800, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'gateio':   {'max_weight_per_min': 1800, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'coinbase': {'max_weight_per_min': 1200, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'kraken':   {'max_weight_per_min': 1200, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5}
}
RATE_LIMIT_SAFETY_BUFFER = 0.85 # Self-throttle when reaching 85% of allowed weight capacity

# Taker & Maker Fee Rates per Exchange (Standard spot tier & VIP tiers)
FEE_RATES = {
    'binance': {'taker': 0.0010, 'maker': 0.0008, 'futures_taker': 0.0004},
    'kraken': {'taker': 0.0026, 'maker': 0.0016, 'futures_taker': 0.0005},
    'coinbase': {'taker': 0.0060, 'maker': 0.0040, 'futures_taker': 0.0010},
    'bybit': {'taker': 0.0010, 'maker': 0.0010, 'futures_taker': 0.00055},
    'okx': {'taker': 0.0010, 'maker': 0.0008, 'futures_taker': 0.0005},
    'gateio': {'taker': 0.0020, 'maker': 0.0015, 'futures_taker': 0.0005}
}

# Minimum profit target threshold in USDT per unit trade
MIN_NET_PROFIT_USDT = 0.50

# --- Phase 3 & 4 Institutional Resilience & Safety Settings ---
# Quote Timestamp Drift: Strict at 35ms to prevent HFT staleness within regional clusters
MAX_QUOTE_AGE_DELTA_MS = 35.0

# Watchdog timeout: Disconnect if no message received within this threshold (in seconds)
WATCHDOG_IDLE_TIMEOUT_SEC = 5.0

# Inventory Rebalancing & Execution Bounds
MIN_INVENTORY_RATIO = 0.10 # 10%
DYNAMIC_TRADE_SIZE_RATIO = 0.25 # Utilize 25% of available exchange inventory per arb trade

# Production Logging & POSIX Shared Memory settings
LOG_CSV_PATH = os.path.join(os.path.dirname(__file__), "live_production_opportunities.csv")
LOG_TO_CSV = True
TELEMETRY_INTERVAL_SEC = 5
IPC_SHARED_MEMORY_NAME = "arb_l2_shared_mem"

