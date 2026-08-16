import os

# Multi-Crypto Pair Symbol Mappings per Exchange
# High-frequency USD/USDT primary market books across 10 major assets
PAIRS_CONFIG = {
    'BTC': {
        'binance': 'btcusdt',
        'kraken': 'XBT/USD',
        'coinbase': 'BTC-USD',
        'bybit': 'BTCUSDT',
        'okx': 'BTC-USDT',
        'gateio': 'BTC_USDT'
    },
    'ETH': {
        'binance': 'ethusdt',
        'kraken': 'ETH/USD',
        'coinbase': 'ETH-USD',
        'bybit': 'ETHUSDT',
        'okx': 'ETH-USDT',
        'gateio': 'ETH_USDT'
    },
    'SOL': {
        'binance': 'solusdt',
        'kraken': 'SOL/USD',
        'coinbase': 'SOL-USD',
        'bybit': 'SOLUSDT',
        'okx': 'SOL-USDT',
        'gateio': 'SOL_USDT'
    },
    'XRP': {
        'binance': 'xrpusdt',
        'kraken': 'XRP/USD',
        'coinbase': 'XRP-USD',
        'bybit': 'XRPUSDT',
        'okx': 'XRP-USDT',
        'gateio': 'XRP_USDT'
    },
    'DOGE': {
        'binance': 'dogeusdt',
        'kraken': 'DOGE/USD',
        'coinbase': 'DOGE-USD',
        'bybit': 'DOGEUSDT',
        'okx': 'DOGE-USDT',
        'gateio': 'DOGE_USDT'
    },
    'AVAX': {
        'binance': 'avaxusdt',
        'kraken': 'AVAX/USD',
        'coinbase': 'AVAX-USD',
        'bybit': 'AVAXUSDT',
        'okx': 'AVAX-USDT',
        'gateio': 'AVAX_USDT'
    },
    'LINK': {
        'binance': 'linkusdt',
        'kraken': 'LINK/USD',
        'coinbase': 'LINK-USD',
        'bybit': 'LINKUSDT',
        'okx': 'LINK-USDT',
        'gateio': 'LINK_USDT'
    },
    'ADA': {
        'binance': 'adausdt',
        'kraken': 'ADA/USD',
        'coinbase': 'ADA-USD',
        'bybit': 'ADAUSDT',
        'okx': 'ADA-USDT',
        'gateio': 'ADA_USDT'
    },
    'BNB': {
        'binance': 'bnbusdt',
        'kraken': 'BNB/USD',
        'coinbase': 'BNB-USD',
        'bybit': 'BNBUSDT',
        'okx': 'BNB-USDT',
        'gateio': 'BNB_USDT'
    },
    'NEAR': {
        'binance': 'nearusdt',
        'kraken': 'NEAR/USD',
        'coinbase': 'NEAR-USD',
        'bybit': 'NEARUSDT',
        'okx': 'NEAR-USDT',
        'gateio': 'NEAR_USDT'
    }
}

# --- Phase 4 Regional Co-Location Clustering ---
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

# In shadow testing / paper trading mode on cloud (Render), allow cross-venue comparisons across all 6 exchanges
ALLOW_CROSS_REGION_DEMO = os.environ.get("ALLOW_CROSS_REGION_DEMO", "true").lower() == "true"

# --- Phase 4 Exchange Rate Limit & Token Bucket Weight Settings ---
API_RATE_LIMITS = {
    'binance':  {'max_weight_per_min': 2400, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'bybit':    {'max_weight_per_min': 2000, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'okx':      {'max_weight_per_min': 1800, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'gateio':   {'max_weight_per_min': 1800, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'coinbase': {'max_weight_per_min': 1200, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5},
    'kraken':   {'max_weight_per_min': 1200, 'order_weight': 2, 'cancel_weight': 1, 'snapshot_weight': 5}
}
RATE_LIMIT_SAFETY_BUFFER = 0.85

# Institutional / Tier-1 Fee Rates per Exchange (0.04% - 0.08% Maker/Taker blends)
FEE_RATES = {
    'binance': {'taker': 0.0004, 'maker': 0.0002, 'futures_taker': 0.0004},
    'kraken': {'taker': 0.0008, 'maker': 0.0004, 'futures_taker': 0.0005},
    'coinbase': {'taker': 0.0010, 'maker': 0.0006, 'futures_taker': 0.0010},
    'bybit': {'taker': 0.0004, 'maker': 0.0002, 'futures_taker': 0.00055},
    'okx': {'taker': 0.0004, 'maker': 0.0002, 'futures_taker': 0.0005},
    'gateio': {'taker': 0.0008, 'maker': 0.0004, 'futures_taker': 0.0005}
}

# Minimum profit target threshold in USDT per executed trade
MIN_NET_PROFIT_USDT = float(os.environ.get("MIN_NET_PROFIT_USDT", 0.01)) # $0.01 min net profit on trade
MIN_NET_SPREAD_PCT = float(os.environ.get("MIN_NET_SPREAD_PCT", 0.00005)) # 0.005% min margin after maker/taker fees

# Quote Timestamp Drift:
# In cloud relaxed simulation mode, tolerance is 60,000ms (60 seconds) so public cloud network jitter doesn't block paper trades.
MAX_QUOTE_AGE_DELTA_MS = float(os.environ.get("MAX_QUOTE_AGE_DELTA_MS", 60000.0))

# Watchdog timeout
WATCHDOG_IDLE_TIMEOUT_SEC = 30.0

# Inventory Rebalancing & Execution Bounds
MIN_INVENTORY_RATIO = 0.10 # 10%
DYNAMIC_TRADE_SIZE_RATIO = 0.25 # Utilize 25% of available exchange inventory per arb trade

# Production Logging & POSIX Shared Memory settings
LOG_CSV_PATH = os.path.join(os.path.dirname(__file__), "paper_trading_ledger.csv")
LOG_TO_CSV = True
TELEMETRY_INTERVAL_SEC = 5
IPC_SHARED_MEMORY_NAME = "arb_l2_shared_mem"
