import os

# =====================================================================
# INSTITUTIONAL BARE-METAL HFT ARBITRAGE ENGINE CONFIGURATION
# Optimized for AWS Tokyo (ap-northeast-1) Bare-Metal EC2 Co-Location
# =====================================================================

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
    },
    'XRP': {
        'binance': 'xrpusdt',
        'kraken': 'XRP/USDT',
        'coinbase': 'XRP-USDT',
        'bybit': 'XRPUSDT',
        'okx': 'XRP-USDT',
        'gateio': 'XRP_USDT'
    },
    'DOGE': {
        'binance': 'dogeusdt',
        'kraken': 'DOGE/USDT',
        'coinbase': 'DOGE-USDT',
        'bybit': 'DOGEUSDT',
        'okx': 'DOGE-USDT',
        'gateio': 'DOGE_USDT'
    },
    'AVAX': {
        'binance': 'avaxusdt',
        'kraken': 'AVAX/USDT',
        'coinbase': 'AVAX-USDT',
        'bybit': 'AVAXUSDT',
        'okx': 'AVAX-USDT',
        'gateio': 'AVAX_USDT'
    },
    'LINK': {
        'binance': 'linkusdt',
        'kraken': 'LINK/USDT',
        'coinbase': 'LINK-USDT',
        'bybit': 'LINKUSDT',
        'okx': 'LINK-USDT',
        'gateio': 'LINK_USDT'
    },
    'ADA': {
        'binance': 'adausdt',
        'kraken': 'ADA/USDT',
        'coinbase': 'ADA-USDT',
        'bybit': 'ADAUSDT',
        'okx': 'ADA-USDT',
        'gateio': 'ADA_USDT'
    },
    'BNB': {
        'binance': 'bnbusdt',
        'kraken': 'BNB/USDT',
        'coinbase': 'BNB-USDT',
        'bybit': 'BNBUSDT',
        'okx': 'BNB-USDT',
        'gateio': 'BNB_USDT'
    },
    'NEAR': {
        'binance': 'nearusdt',
        'kraken': 'NEAR/USDT',
        'coinbase': 'NEAR-USDT',
        'bybit': 'NEARUSDT',
        'okx': 'NEAR-USDT',
        'gateio': 'NEAR_USDT'
    }
}

# --- Phase 4 Regional Co-Location Clustering ---
# Strict optical speed-of-light boundary: only co-located venues within the same physical datacenter cluster are evaluated!
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

# Cross-Region Cluster Execution Flag:
# STRICT FALSE for bare-metal institutional production: eliminates ~150ms optical fiber lag and prevents toxic out-of-region fills!
ALLOW_CROSS_REGION_DEMO = False

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

# Standard Exchange Fee Rates
FEE_RATES = {
    'binance': {'taker': 0.0010, 'maker': 0.0008, 'futures_taker': 0.0004},
    'kraken': {'taker': 0.0026, 'maker': 0.0016, 'futures_taker': 0.0005},
    'coinbase': {'taker': 0.0060, 'maker': 0.0040, 'futures_taker': 0.0010},
    'bybit': {'taker': 0.0010, 'maker': 0.0010, 'futures_taker': 0.00055},
    'okx': {'taker': 0.0010, 'maker': 0.0008, 'futures_taker': 0.0005},
    'gateio': {'taker': 0.0020, 'maker': 0.0015, 'futures_taker': 0.0005}
}

# Strict Minimum Net Profit Hurdle per Executed Trade
MIN_NET_PROFIT_USDT = float(os.environ.get("MIN_NET_PROFIT_USDT", 0.50)) # $0.50 min net profit on trade
MIN_NET_SPREAD_PCT = float(os.environ.get("MIN_NET_SPREAD_PCT", 0.0002)) # 0.02% min net margin after fees

# Strict Quote Timestamp Drift:
# In bare-metal co-located production (AWS Tokyo with PTP Chrony hardware time sync),
# tolerance is strictly capped at 35.0ms to mathematically eliminate time-warped phantom spreads.
MAX_QUOTE_AGE_DELTA_MS = float(os.environ.get("MAX_QUOTE_AGE_DELTA_MS", 35.0))

# Watchdog idle timeout
WATCHDOG_IDLE_TIMEOUT_SEC = 5.0

# Inventory Rebalancing & Execution Bounds
MIN_INVENTORY_RATIO = 0.10 # 10%
DYNAMIC_TRADE_SIZE_RATIO = 0.25 # Utilize 25% of available exchange inventory per arb trade

# Production Logging & POSIX Shared Memory settings
LOG_CSV_PATH = os.path.join(os.path.dirname(__file__), "paper_trading_ledger.csv")
LOG_TO_CSV = True
TELEMETRY_INTERVAL_SEC = 5
IPC_SHARED_MEMORY_NAME = "arb_l2_shared_mem"
