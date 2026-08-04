import time
from typing import Dict, Optional
from config import API_RATE_LIMITS, RATE_LIMIT_SAFETY_BUFFER

class TokenBucketRateLimiter:
    """
    Real-time Token / Leaky Bucket API Weight consumption monitor with HTTP Header Synchronization.
    Protects the system from exceeding exchange REST/WS rate limits during massive volatility bursts,
    preventing catastrophic HTTP 429 (Too Many Requests) and HTTP 418 (I'm a teapot / IP Auto-Ban).
    
    Incorporates real-time authoritative header sync (e.g. X-MBX-USED-WEIGHT-1M) and error penalty
    weight adjustments to eliminate local Token Bucket desync.
    """
    def __init__(self, limits: Optional[Dict[str, Dict]] = None, safety_buffer: float = RATE_LIMIT_SAFETY_BUFFER):
        self.limits = limits or API_RATE_LIMITS
        self.safety_buffer = safety_buffer
        
        # Track active bucket states per venue
        self.buckets: Dict[str, Dict] = {}
        now = time.monotonic()
        
        for ex, conf in self.limits.items():
            max_capacity = conf['max_weight_per_min'] * self.safety_buffer
            self.buckets[ex] = {
                'capacity': max_capacity,
                'max_raw_weight': conf['max_weight_per_min'],
                'tokens': max_capacity,  # Tokens represent remaining available API weight
                'replenish_rate_per_sec': max_capacity / 60.0,
                'last_update_monotonic': now,
                'total_weight_consumed': 0,
                'throttled_count': 0,
                'header_sync_count': 0,
                'penalty_weight_applied': 0
            }

    def _replenish(self, exchange: str):
        bucket = self.buckets.get(exchange)
        if not bucket:
            return
        now = time.monotonic()
        elapsed_sec = max(0.0, now - bucket['last_update_monotonic'])
        if elapsed_sec > 0:
            added_tokens = elapsed_sec * bucket['replenish_rate_per_sec']
            bucket['tokens'] = min(bucket['capacity'], bucket['tokens'] + added_tokens)
            bucket['last_update_monotonic'] = now

    def sync_with_exchange_header(self, exchange: str, used_weight_header: int, penalty_occurred: bool = False):
        """
        Overwrites local Token Bucket calculations with the ground-truth weight returned by exchange HTTP headers 
        (e.g., Binance X-MBX-USED-WEIGHT-1M or X-MBX-ORDER-COUNT-10S).
        Eliminates fatal drift caused by rejected request penalty weighting (HTTP 400/422 spam penalties).
        """
        exchange = exchange.lower()
        if exchange not in self.buckets:
            return
        
        self._replenish(exchange)
        bucket = self.buckets[exchange]
        
        # Authoritative ground-truth remaining capacity based on real exchange counter
        real_remaining_weight = max(0.0, bucket['max_raw_weight'] - float(used_weight_header))
        safe_remaining = min(bucket['capacity'], real_remaining_weight * self.safety_buffer)
        
        # If exchange reports lower capacity than our local estimate, adjust immediately
        if safe_remaining < bucket['tokens'] or penalty_occurred:
            discrepancy = max(0.0, bucket['tokens'] - safe_remaining)
            bucket['tokens'] = safe_remaining
            bucket['header_sync_count'] += 1
            if penalty_occurred:
                bucket['penalty_weight_applied'] += int(discrepancy)
                print(f" [⚖️ HTTP HEADER SYNC PENALTY: {exchange.upper()}] Exchange ground-truth applied! Intercepted error penalty weight (-{int(discrepancy)} tokens). Capacity recalibrated to {bucket['tokens']:.0f}.")

    def record_error_penalty(self, exchange: str, penalty_weight: int = 50):
        """Applies immediate penalty reduction on rejected or malformed API responses."""
        exchange = exchange.lower()
        if exchange in self.buckets:
            self._replenish(exchange)
            self.buckets[exchange]['tokens'] = max(0.0, self.buckets[exchange]['tokens'] - penalty_weight)
            self.buckets[exchange]['penalty_weight_applied'] += penalty_weight
            print(f" [🛑 API ERROR PENALTY APPLIED: {exchange.upper()}] Deducted {penalty_weight} weight tokens for malformed/rejected request.")

    def can_consume(self, exchange: str, action: str = 'order_weight') -> bool:
        """
        Checks if executing the specified API action is safe within institutional weight thresholds.
        If capacity is depleted, self-throttles the execution before the exchange issues an auto-ban.
        """
        exchange = exchange.lower()
        if exchange not in self.buckets:
            return True # Unknown venue defaults to proceed
            
        self._replenish(exchange)
        bucket = self.buckets[exchange]
        conf = self.limits.get(exchange, {})
        
        cost = conf.get(action, conf.get('order_weight', 2))
        
        if bucket['tokens'] >= cost:
            bucket['tokens'] -= cost
            bucket['total_weight_consumed'] += cost
            return True
        else:
            bucket['throttled_count'] += 1
            print(f"\n[🛑 API AUTO-THROTTLE: {exchange.upper()}] Weight cap ({bucket['capacity']:.0f}/min) approached! Order execution self-throttled to prevent HTTP 418 IP auto-ban.")
            return False

    def check_and_consume(self, exchange: str, action: str = 'order_weight') -> bool:
        """Alias for can_consume to support intuitive transactional checks."""
        return self.can_consume(exchange, action)

    def get_telemetry(self) -> Dict[str, Dict]:
        self._replenish_all()
        stats = {}
        for ex, b in self.buckets.items():
            pct_remaining = (b['tokens'] / b['capacity']) * 100.0 if b['capacity'] > 0 else 0.0
            stats[ex] = {
                "remaining_pct": round(pct_remaining, 1),
                "consumed_weight": b['total_weight_consumed'],
                "throttled_events": b['throttled_count'],
                "header_syncs": b['header_sync_count'],
                "penalties_applied": b['penalty_weight_applied']
            }
        return stats

    def _replenish_all(self):
        for ex in self.buckets:
            self._replenish(ex)
