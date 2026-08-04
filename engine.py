import time
import itertools
from config import FEE_RATES, MIN_NET_PROFIT_USDT, PAIRS_CONFIG, MAX_QUOTE_AGE_DELTA_MS, REGIONAL_CLUSTERS
from watchdog import SequenceValidator, TimestampSyncValidator, Watchdog
from inventory_manager import InventoryManager
from ipc_manager import SharedMemoryIPCManager
from rate_limiter import TokenBucketRateLimiter
from analytics_engine import TradeReconciliationDatabase
from circuit_breaker import MultiTierDrawdownKillSwitch
from latency_profiler import ExecutionLatencyProfiler
from futures_hedger import PerpetualFuturesHedger

class ArbitrageEngine:
    def __init__(self, logger=None, use_ipc=False):
        self.logger = logger
        self.inventory_mgr = InventoryManager()
        self.rate_limiter = TokenBucketRateLimiter()
        self.futures_hedger = PerpetualFuturesHedger()
        self.analytics_db = TradeReconciliationDatabase()
        self.circuit_breaker = MultiTierDrawdownKillSwitch()
        self.latency_profiler = ExecutionLatencyProfiler()
        self.seq_validator = SequenceValidator()
        self.timestamp_validator = TimestampSyncValidator(max_delta_ms=MAX_QUOTE_AGE_DELTA_MS)
        self.watchdog = Watchdog()
        
        self.exchanges = list(FEE_RATES.keys())
        self.symbols = list(PAIRS_CONFIG.keys())
        
        self.use_ipc = use_ipc
        self.ipc = None
        if self.use_ipc:
            try:
                self.ipc = SharedMemoryIPCManager(create=False)
            except FileNotFoundError:
                print("[⚠️ ENGINE NOTE] Shared memory buffer not found; defaulting to in-memory event callback mode.")
                self.use_ipc = False

        # Map each exchange to its geographical region cluster (Tokyo vs N. Virginia)
        self.exchange_cluster_map = {}
        for region_id, data in REGIONAL_CLUSTERS.items():
            for ex in data['exchanges']:
                self.exchange_cluster_map[ex] = region_id

        # Shared multi-pair orderbook memory state
        self.orderbooks = {}
        for sym in self.symbols:
            for ex in self.exchanges:
                self.orderbooks[(sym, ex)] = {
                    'bid': 0.0, 
                    'ask': 0.0, 
                    'updated_ns': 0,
                    'server_ts_ms': 0,
                    'seq': 0
                }
        
        # Performance & Phase 4 Institutional Metrics
        self.eval_count = 0
        self.opportunity_count = 0
        self.ghost_arbitrage_rejected = 0
        self.sequence_gaps_rejected = 0
        self.cross_region_skipped = 0
        self.latency_samples = []

    def update_orderbook(self, symbol, exchange, bid, ask, recv_ns, server_ts_ms=None, seq_id=None):
        """Called directly by WebSocket workers on tick receipt (or by loop in isolated process architecture)."""
        key = (symbol, exchange)
        if key not in self.orderbooks:
            return

        self.watchdog.record_heartbeat(exchange, symbol)

        # 1. Sequence Validation Check
        if not self.seq_validator.validate_sequence(exchange, symbol, seq_id):
            self.sequence_gaps_rejected += 1
            return # Drop desynced/out-of-order packet

        self.orderbooks[key]['bid'] = float(bid)
        self.orderbooks[key]['ask'] = float(ask)
        self.orderbooks[key]['updated_ns'] = int(recv_ns)
        self.orderbooks[key]['server_ts_ms'] = server_ts_ms or int(time.time() * 1000)
        self.orderbooks[key]['seq'] = seq_id or 0

        # Trigger microsecond evaluation for this specific symbol
        self.evaluate_symbol(symbol)

    def fetch_ipc_snapshots(self, symbol):
        """Fetches real-time L2 orderbook quotes directly from POSIX Shared Memory lock-free."""
        if not self.ipc:
            return
        quotes = self.ipc.read_all_quotes_for_symbol(symbol)
        for ex, data in quotes.items():
            key = (symbol, ex)
            if key in self.orderbooks:
                self.orderbooks[key]['bid'] = data['bid']
                self.orderbooks[key]['ask'] = data['ask']
                self.orderbooks[key]['server_ts_ms'] = data['timestamp_ms']
                self.orderbooks[key]['seq'] = data['sequence']

    def evaluate_symbol(self, symbol):
        t_start = time.perf_counter_ns()
        
        # If in isolated worker IPC mode, fetch latest zero-copy state from shared memory
        if self.use_ipc and self.ipc:
            self.fetch_ipc_snapshots(symbol)

        # Cross-exchange matrix evaluation for this symbol
        for ex1, ex2 in itertools.permutations(self.exchanges, 2):
            # 1. Phase 4 Geographic Cluster Isolation
            # Overcomes ~150ms optical speed-of-light delay between Tokyo and Virginia nodes.
            # Deterministic latency arbitrage is strictly limited to same-cluster venues!
            if self.exchange_cluster_map.get(ex1) != self.exchange_cluster_map.get(ex2):
                self.cross_region_skipped += 1
                continue

            book1 = self.orderbooks[(symbol, ex1)]
            book2 = self.orderbooks[(symbol, ex2)]

            ask1 = book1['ask'] # Buy price on Ex1
            bid2 = book2['bid'] # Sell price on Ex2

            if ask1 <= 0.0 or bid2 <= 0.0:
                continue

            # 2. Timestamp Drift Validator ("Ghost Arbitrage" Protection)
            ts1 = book1['server_ts_ms']
            ts2 = book2['server_ts_ms']
            is_fresh, age_delta_ms = self.timestamp_validator.validate_quote_freshness(ts1, ts2)

            if not is_fresh:
                self.ghost_arbitrage_rejected += 1
                continue # Reject time-warped ghost spread (> 35ms delta)

            # Retrieve taker fee rates for both venues
            fee_buy = FEE_RATES[ex1]['taker']
            fee_sell = FEE_RATES[ex2]['taker']

            # Calculate Net Profit per unit after fees
            net_profit = bid2 * (1.0 - fee_sell) - ask1 * (1.0 + fee_buy)
            gross_spread = bid2 - ask1

            if net_profit >= MIN_NET_PROFIT_USDT:
                t_end = time.perf_counter_ns()
                eval_micros = (t_end - t_start) / 1000.0
                self.opportunity_count += 1
                
                # 3. Phase 4 Token Bucket Rate Limit Check (Prevents HTTP 429 & HTTP 418 IP auto-ban)
                if not (self.rate_limiter.can_consume(ex1, 'order_weight') and self.rate_limiter.can_consume(ex2, 'order_weight')):
                    print(f" [🛑 EXECUTION ABORTED: {ex1.upper()} <-> {ex2.upper()}] API Weight quota saturated! Trade self-throttled to avoid HTTP 418 ban.")
                    continue

                # Phase 7: Check Multi-Tier Drawdown Kill-Switch clearance
                perm = self.circuit_breaker.verify_execution_permission()
                if not perm['can_execute']:
                    print(f" [🛡️ KILL-SWITCH SHIELD ACTIVE] Trade execution blocked: {perm['reason']}")
                    continue

                # Calculate optimal dynamic order size based on real available capital inventory
                dynamic_units = self.inventory_mgr.get_dynamic_order_size(
                    buy_ex=ex1, 
                    sell_ex=ex2, 
                    asset=symbol, 
                    buy_price=ask1, 
                    target_usdt=600.0, 
                    max_ratio=0.25
                )
                
                # Phase 7: Audit Execution Latency Profiles (p50/p99/p99.9) for matching engine congestion
                lat_audit1 = self.latency_profiler.audit_routing_feasibility(ex1, dynamic_units)
                lat_audit2 = self.latency_profiler.audit_routing_feasibility(ex2, dynamic_units)
                if not (lat_audit1["clearance"] and lat_audit2["clearance"]):
                    print(f" [⏱️ LATENCY ROUTER BYPASS] Severe p99 latency (>180ms) detected on {ex1.upper()}/{ex2.upper()}. Bypassing venue to avoid fill slippage!")
                    continue
                dynamic_units = min(lat_audit1["allowed_units"], lat_audit2["allowed_units"])
                
                print(f"\n[⚡ PHASE 7 VALIDATED ARBITRAGE] Asset: {symbol} (Quote Age Delta: {age_delta_ms:.1f}ms | Cluster: {self.exchange_cluster_map[ex1]})")
                print(f"   Buy {ex1.upper():<8} @ ${ask1:.4f} -> Sell {ex2.upper():<8} @ ${bid2:.4f}")
                print(f"   Gross Spread: ${gross_spread:.4f}/unit | Net Profit: ${net_profit:.4f}/unit | Sizing: {dynamic_units:.4f} units | Eval Time: {eval_micros:.2f} µs")

                # Phase 7: Record in Trade Reconciliation Database using unbiased Global Composite Consensus ($P_{composite}$)
                self.analytics_db.record_and_reconcile_trade(
                    symbol=symbol,
                    buy_ex=ex1,
                    buy_price=ask1,
                    sell_ex=ex2,
                    sell_price=bid2,
                    qty=dynamic_units,
                    expected_spread=gross_spread,
                    orderbooks_snapshot=books,
                    cluster_name=self.exchange_cluster_map.get(ex1, "tokyo")
                )

                # Production Inventory & Kill-Switch Reconciliation
                # Track realized balance adjustments across local reserves and update daily PnL drawdown protection
                self.inventory_mgr.balances[ex1]['USDT'] -= ask1 * dynamic_units
                self.inventory_mgr.balances[ex1][symbol] = self.inventory_mgr.balances[ex1].get(symbol, 0.0) + dynamic_units
                self.inventory_mgr.balances[ex2][symbol] = max(0.0, self.inventory_mgr.balances[ex2].get(symbol, 0.0) - dynamic_units)
                self.inventory_mgr.balances[ex2]['USDT'] += bid2 * dynamic_units
                
                realized_trade_profit = net_profit * dynamic_units
                self.circuit_breaker.report_trade_execution_outcome(is_success=True, realized_pnl_delta=realized_trade_profit)

                if self.logger:
                    self.logger.log_opportunity(ex1, ask1, ex2, bid2, gross_spread, net_profit, eval_micros)

        t_end = time.perf_counter_ns()
        eval_micros = (t_end - t_start) / 1000.0
        self.latency_samples.append(eval_micros)
        self.eval_count += 1

    def get_telemetry_snapshot(self):
        if not self.latency_samples:
            return None
        avg_lat = sum(self.latency_samples) / len(self.latency_samples)
        min_lat = min(self.latency_samples)
        max_lat = max(self.latency_samples)
        count = len(self.latency_samples)
        self.latency_samples.clear()
        
        books_snapshot = {}
        for sym in self.symbols:
            books_snapshot[sym] = {}
            for ex in self.exchanges:
                books_snapshot[sym][ex] = dict(self.orderbooks[(sym, ex)])

        inventory_health = self.inventory_mgr.audit_inventory_health()
        
        # Pull Phase 4 Futures Hedging & Chase Protocol Metrics
        hedger_metrics = self.futures_hedger.get_telemetry_metrics()
        rate_limit_metrics = self.rate_limiter.get_telemetry()

        return {
            'count': count,
            'opp_count': self.opportunity_count,
            'ghost_rejected': self.ghost_arbitrage_rejected,
            'seq_rejected': self.sequence_gaps_rejected,
            'cross_region_skipped': self.cross_region_skipped,
            'torn_reads_blocked': self.ipc.torn_reads_prevented if (self.use_ipc and self.ipc) else 0,
            'avg_lat': avg_lat,
            'min_lat': min_lat,
            'max_lat': max_lat,
            'inventory_health': inventory_health,
            'futures_hedger': hedger_metrics,
            'rate_limits': rate_limit_metrics,
            'analytics_toxicity': self.analytics_db.get_telemetry_metrics(),
            'circuit_breaker': self.circuit_breaker.get_telemetry_metrics(),
            'latency_profiles': self.latency_profiler.get_telemetry_metrics(),
            'books': books_snapshot
        }
