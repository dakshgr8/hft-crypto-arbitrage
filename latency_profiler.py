import time
from typing import Dict, List

class ExecutionLatencyProfiler:
    """
    Execution Latency Profiler & Dynamic Venue Routing Engine (Phase 7 Capital Shield).
    
    Tracks execution Round-Trip Time (RTT) percentiles (p50, p99, p99.9) for real REST/WebSocket order submissions
    per exchange. If an exchange's p99 latency spikes above 120 ms (indicating matching engine congestion, 
    AWS internal network buffering, or DDoS mitigating filters), the engine temporarily reduces capital 
    sizing allocation or automatically bypasses that venue until execution latency normalizes.
    
    All history arrays use strict bounded ring-buffers to guarantee immunity against Linux tmpfs OOM killer termination.
    """
    def __init__(self, p99_throttle_threshold_ms: float = 120.0):
        self.p99_threshold_ms = p99_throttle_threshold_ms
        self.rtt_samples: Dict[str, List[float]] = {}
        self.venue_status: Dict[str, str] = {}
        self.throttled_events: int = 0
        self.bypassed_orders_count: int = 0
        
        exchanges = ['binance', 'kraken', 'coinbase', 'bybit', 'okx', 'gateio']
        for ex in exchanges:
            # Initialize with standard expected AWS internal routing latency baseline (20ms) until real order fills stream in
            self.rtt_samples[ex] = [20.0]
            self.venue_status[ex] = "OPTIMAL (Full Allocation)"

    def record_rtt_sample(self, exchange: str, rtt_ms: float):
        """Records a real-time order execution or health-check Ping RTT in milliseconds."""
        ex = exchange.lower()
        if ex not in self.rtt_samples:
            self.rtt_samples[ex] = []
            
        self.rtt_samples[ex].append(round(rtt_ms, 2))
        # Rigid ring buffer bound to preserve system RAM under Linux OOM monitoring
        if len(self.rtt_samples[ex]) > 50:
            self.rtt_samples[ex].pop(0)
            
        self._evaluate_venue_latency(ex)

    def _evaluate_venue_latency(self, exchange: str):
        samples = sorted(self.rtt_samples[exchange])
        n = len(samples)
        if n < 1:
            return
            
        p99_idx = int(0.99 * (n - 1))
        p99_lat = samples[p99_idx]
        
        old_status = self.venue_status.get(exchange, "")
        if p99_lat >= self.p99_threshold_ms:
            self.venue_status[exchange] = f"⚠️ CONGESTED_THROTTLE (p99: {p99_lat:.1f}ms >= 120ms)"
            self.throttled_events += 1
            if "CONGESTED" not in old_status:
                print(f"\n[⏱️ LATENCY PROFILER SHIELD: {exchange.upper()}] p99 RTT spiked to {p99_lat:.1f}ms! Matching engine congested; reducing capital sizing allocation by 50% and engaging dynamic bypass.\n")
        else:
            self.venue_status[exchange] = "OPTIMAL (Full Allocation)"

    def audit_routing_feasibility(self, exchange: str, desired_units: float) -> Dict:
        """
        Invoked before executing an arbitrage leg. Returns dynamic allocation sizing and routing clearance.
        """
        ex = exchange.lower()
        samples = sorted(self.rtt_samples.get(ex, [20.0]))
        n = len(samples)
        p99_lat = samples[int(0.99 * (n - 1))] if n > 0 else 20.0
        
        if p99_lat >= (self.p99_threshold_ms * 1.5):
            # Severe lag (>180ms): Complete routing bypass to prevent fill slippage
            self.bypassed_orders_count += 1
            return {"clearance": False, "allowed_units": 0.0, "p99_ms": p99_lat, "status": "BYPASSED (Severe Congestion)"}
        elif p99_lat >= self.p99_threshold_ms:
            # Moderate congestion (120ms-180ms): Throttle capital sizing by 50%
            return {"clearance": True, "allowed_units": desired_units * 0.5, "p99_ms": p99_lat, "status": "THROTTLED (50% Allocation)"}
        else:
            return {"clearance": True, "allowed_units": desired_units, "p99_ms": p99_lat, "status": "FULL_CLEARANCE"}

    def get_telemetry_metrics(self) -> Dict:
        stats = {}
        for ex, samples in self.rtt_samples.items():
            sorted_s = sorted(samples)
            n = len(sorted_s)
            p50 = sorted_s[n // 2] if n > 0 else 0.0
            p99 = sorted_s[int(0.99 * (n - 1))] if n > 0 else 0.0
            p999 = sorted_s[int(0.999 * (n - 1))] if n > 0 else 0.0
            stats[ex] = {"p50": p50, "p99": p99, "p99_9": p999, "status": self.venue_status.get(ex, "UNKNOWN")}
            
        return {
            "venue_profiles": stats,
            "throttled_events": self.throttled_events,
            "orders_bypassed": self.bypassed_orders_count
        }
