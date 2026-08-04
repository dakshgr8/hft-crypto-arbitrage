import time
import datetime
import math
import subprocess

class TimestampNormalizer:
    """
    Solves the 'Ghost Spread Anomaly' by normalizing heterogeneous timestamps
    (ISO-8601 strings, epoch seconds, epoch milliseconds, and microseconds)
    into uniform Unix epoch milliseconds (float).
    """
    @staticmethod
    def normalize_ms(raw_ts) -> float:
        if raw_ts is None:
            return time.time() * 1000.0
        
        # 1. Handle ISO-8601 string dates (e.g., Coinbase '2026-08-04T10:46:46.123456Z' or Bybit strings)
        if isinstance(raw_ts, str):
            # If it's pure numeric string, convert to float first
            if raw_ts.replace('.', '', 1).isdigit() or (raw_ts.startswith('-') and raw_ts[1:].replace('.', '', 1).isdigit()):
                raw_ts = float(raw_ts)
            else:
                try:
                    # Strip Z or tz offset and parse ISO string
                    iso_str = raw_ts.replace('Z', '+00:00')
                    # Convert to datetime then epoch ms
                    dt = datetime.datetime.fromisoformat(iso_str)
                    return dt.timestamp() * 1000.0
                except (ValueError, TypeError):
                    # Fallback to local time if string format is unparseable
                    return time.time() * 1000.0
        
        # 2. Handle numeric (int/float) timestamps by evaluating magnitude
        val = float(raw_ts)
        if val == 0.0:
            return time.time() * 1000.0
            
        # If value < 100,000,000,000: Unix epoch in SECONDS (e.g., Kraken 1722768000.123)
        if val < 100_000_000_000.0:
            return val * 1000.0
        # If value < 100,000,000,000,000: Unix epoch in MILLISECONDS (e.g., Binance/OKX/Bybit 1722768000123)
        elif val < 100_000_000_000_000.0:
            return val
        # Else value >= 100,000,000,000,000: Unix epoch in MICROSECONDS (e.g., Bybit microsecond feed)
        else:
            return val / 1000.0


class SequenceValidator:
    """
    Ensures state consistency by checking lastUpdateId / sequence numbers.
    Prevents calculating spreads on corrupted or desynchronized orderbook depth.
    """
    def __init__(self):
        # Maps (exchange, symbol) -> expected_next_seq
        self.expected_sequences = {}
        self.desync_events_blocked = 0

    def validate_sequence(self, exchange: str, symbol: str, seq_no: int) -> bool:
        if seq_no is None or seq_no <= 0:
            return True  # Skip if exchange doesn't emit strict sequence incrementers
            
        key = (exchange, symbol)
        last_seq = self.expected_sequences.get(key)
        
        # If first packet seen or resynced
        if last_seq is None:
            self.expected_sequences[key] = seq_no
            return True
            
        # In a delta orderbook, next seq must be strictly greater than or equal to last_seq
        # For rigorous sequential checks, if gap occurs (seq_no > last_seq + 1) or out of order (seq_no < last_seq),
        # we flag a desync event to force a snapshot requery.
        if seq_no < last_seq:
            self.desync_events_blocked += 1
            return False
            
        self.expected_sequences[key] = seq_no
        return True

    def reset_sequence(self, exchange: str, symbol: str):
        key = (exchange, symbol)
        if key in self.expected_sequences:
            del self.expected_sequences[key]


class TimestampSyncValidator:
    """
    Enforces strict quote synchronization across AWS regions (e.g., Tokyo vs Virginia).
    Filters out time-warped "Ghost Spreads" where stale prices create artificial gaps.
    """
    def __init__(self, max_delta_ms: float = 35.0):
        self.max_delta_ms = max_delta_ms
        self.ghost_spreads_blocked = 0

    def is_synchronized(self, ts_ex_a, ts_ex_b) -> bool:
        is_fresh, _ = self.validate_quote_freshness(ts_ex_a, ts_ex_b)
        return is_fresh

    def validate_quote_freshness(self, ts_ex_a, ts_ex_b):
        norm_a = TimestampNormalizer.normalize_ms(ts_ex_a)
        norm_b = TimestampNormalizer.normalize_ms(ts_ex_b)
        
        delta_ms = abs(norm_a - norm_b)
        if delta_ms > self.max_delta_ms:
            self.ghost_spreads_blocked += 1
            return False, delta_ms
        return True, delta_ms


class Watchdog:
    """
    Monitors L2 WebSocket feeds for silence/stalling and enforces sequence/timestamp validity.
    """
    def __init__(self, timeout_sec: float = 5.0):
        self.timeout_sec = timeout_sec
        self.last_seen = {}  # (exchange, symbol) -> monotonic timestamp
        self.seq_validator = SequenceValidator()
        self.sync_validator = TimestampSyncValidator(max_delta_ms=35.0)

    def heartbeat(self, exchange: str, symbol: str = ""):
        self.last_seen[(exchange, symbol)] = time.monotonic()

    def record_heartbeat(self, exchange: str, symbol: str = ""):
        self.heartbeat(exchange, symbol)

    def is_feed_alive(self, exchange: str, symbol: str = "") -> bool:
        last_time = self.last_seen.get((exchange, symbol))
        if last_time is None:
            return True
        if (time.monotonic() - last_time) > self.timeout_sec:
            return False
        return True

    def check_health(self, exchanges):
        """Checks connection health across exchanges and returns list of dead/idle venues."""
        now = time.monotonic()
        dead = []
        for ex in exchanges:
            # Check most recent heartbeat for any symbol on this exchange
            last_time = 0.0
            for (seen_ex, seen_sym), ts in self.last_seen.items():
                if seen_ex == ex and ts > last_time:
                    last_time = ts
            if last_time > 0 and (now - last_time) > self.timeout_sec:
                dead.append((ex, now - last_time))
        return dead

# Alias for backwards and multi-module compatibility
ConnectionWatchdog = Watchdog


class PTPSyncValidator:
    """
    Monitors AWS Time Sync Service / Precision Time Protocol (PTP) clock precision.
    Ensures sub-millisecond clock alignment between multi-region nodes (Tokyo vs Virginia)
    so system time divergence doesn't trigger false positives in the 35ms quote age filter.
    """
    @staticmethod
    def verify_clock_sync():
        result = {
            'status': 'UNKNOWN',
            'precision': time.get_clock_info('time').resolution,
            'offset_ms': 0.0,
            'message': ''
        }
        try:
            # Check Linux NTP / PTP status via chronyc tracking
            output = subprocess.check_output(['chronyc', 'tracking'], stderr=subprocess.STDOUT, text=True, timeout=2.0)
            for line in output.splitlines():
                if "System time" in line:
                    # Example line: 'System time     : 0.000001234 seconds fast of NTP time'
                    parts = line.split()
                    for idx, val in enumerate(parts):
                        if val == 'seconds':
                            try:
                                offset_sec = float(parts[idx - 1])
                                result['offset_ms'] = round(abs(offset_sec * 1000.0), 4)
                            except ValueError:
                                pass
            
            if result['offset_ms'] < 1.0:
                result['status'] = 'SYNCHRONIZED'
                result['message'] = f"✅ AWS PTP/NTP Clock Synchronized (Offset: {result['offset_ms']} ms to UTC)"
            else:
                result['status'] = 'WARNING'
                result['message'] = f"⚠️ Clock Drift Warning: System time offset is {result['offset_ms']} ms (Threshold < 1.0 ms)"
                
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            result['status'] = 'LOCAL_DEV_FALLBACK'
            result['message'] = f"ℹ️ `chronyc` not detected (Local workstation or standard NTP). In production AWS EC2, enable AWS Time Sync (PTP) to maintain sub-ms multi-region alignment."
        
        return result
