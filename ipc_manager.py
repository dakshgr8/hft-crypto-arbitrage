import ctypes
from multiprocessing import shared_memory
from typing import Dict, Tuple, List, Optional
import time

# Supported Exchanges and Pairs for Fixed Slot Mapping
EXCHANGES = ['binance', 'kraken', 'coinbase', 'bybit', 'okx', 'gateio']
PAIRS = ['BTC', 'ETH', 'SOL']

class L2QuoteStruct(ctypes.Structure):
    """
    Fixed-memory C struct representing real-time L2 orderbook top quote.
    Implements a Seqlock (Sequence Lock) pattern via `seqlock` counter to eliminate
    torn reads across multi-process boundaries in /dev/shm without heavy OS mutex locks.
    """
    _fields_ = [
        ("seqlock", ctypes.c_uint64),      # Seqlock: odd = write in progress, even = valid read
        ("bid_price", ctypes.c_double),
        ("bid_volume", ctypes.c_double),
        ("ask_price", ctypes.c_double),
        ("ask_volume", ctypes.c_double),
        ("timestamp_ms", ctypes.c_double), # Normalized Unix Epoch ms
        ("sequence", ctypes.c_int64),
        ("is_valid", ctypes.c_uint8)       # 0 = stale/empty, 1 = valid quote
    ]

class SharedMemoryIPCManager:
    """
    Manages lock-free, zero-copy POSIX shared memory communication across isolated OS worker processes.
    Bypasses Python GIL and eliminates Head-of-Line (HoL) Blocking during volatility bursts.
    Incorporates Seqlock read/write atomic integrity to prevent torn reads of double floats.
    """
    def __init__(self, create: bool = True, shm_name: str = "arb_l2_shared_mem"):
        self.shm_name = shm_name
        self.total_slots = len(EXCHANGES) * len(PAIRS)
        self.struct_size = ctypes.sizeof(L2QuoteStruct)
        self.total_bytes = self.total_slots * self.struct_size
        
        # Build deterministic slot mapping: (exchange, symbol) -> index [0 .. total_slots-1]
        self.slot_map: Dict[Tuple[str, str], int] = {}
        idx = 0
        for ex in EXCHANGES:
            for pair in PAIRS:
                self.slot_map[(ex, pair)] = idx
                idx += 1

        self.shm = None
        self.torn_reads_prevented = 0
        self._init_shared_memory(create)

    def _init_shared_memory(self, create: bool):
        if create:
            # Clean up residual shared memory if it exists from a terminated session
            try:
                temp_shm = shared_memory.SharedMemory(name=self.shm_name, create=False)
                temp_shm.close()
                temp_shm.unlink()
            except FileNotFoundError:
                pass
            
            # Create fresh shared memory buffer
            self.shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=self.total_bytes)
            # Zero out buffer
            self.shm.buf[:self.total_bytes] = bytes(self.total_bytes)
        else:
            # Connect to existing shared memory created by main parent process
            self.shm = shared_memory.SharedMemory(name=self.shm_name, create=False)

    def sanitize_seqlock(self, exchange: str):
        """
        Atomic Seqlock Sanitization Protocol (Phase 7 Capital Shield / Respawn Recovery).
        When a worker process restarts after crashing mid-write, its assigned shared memory slot may be stuck at an 
        ODD integer seqlock value. If unaddressed, the central matrix engine will fall into an infinite spin-retry loop 
        or persistently discard valid updates for this venue!
        
        This startup routine scans every symbol slot for the target exchange. If an odd (mid-write) seqlock is found, 
        it resets the sequence to an EVEN integer and invalidates stale data, restoring synchronization immediately.
        """
        ex = exchange.lower()
        sanitized_slots = 0
        for (map_ex, symbol), slot in self.slot_map.items():
            if map_ex == ex:
                offset = slot * self.struct_size
                quote = L2QuoteStruct.from_buffer(self.shm.buf, offset)
                # Check if seqlock is odd (stuck mid-write)
                if quote.seqlock & 1 == 1:
                    quote.is_valid = 0  # Invalidate potentially corrupt mid-write floating data
                    quote.seqlock += 1  # Force increment to an EVEN integer
                    sanitized_slots += 1
        if sanitized_slots > 0:
            print(f" [🛡️ SEQLOCK SANITIZER: {exchange.upper()}] Intercepted and cleared {sanitized_slots} stuck-odd seqlock slots! Shared memory restored to EVEN parity.")

    def write_quote(self, exchange: str, symbol: str, bid_p: float, bid_v: float, ask_p: float, ask_v: float, ts_ms: float, seq: int = 0):
        """
        Invoked by an isolated OS worker process when a real-time orderbook delta arrives.
        Executes zero-copy atomic write into POSIX shared memory protected by Seqlock protocol.
        """
        slot = self.slot_map.get((exchange.lower(), symbol.upper()))
        if slot is None:
            return
        
        offset = slot * self.struct_size
        quote = L2QuoteStruct.from_buffer(self.shm.buf, offset)
        
        # Step 1: Seqlock Write Start (Increment to ODD integer to signify write mid-progress)
        current_seq = quote.seqlock
        quote.seqlock = current_seq + 1
        
        # Step 2: Perform mutational writes on floating point & metadata fields
        quote.bid_price = float(bid_p)
        quote.bid_volume = float(bid_v)
        quote.ask_price = float(ask_p)
        quote.ask_volume = float(ask_v)
        quote.timestamp_ms = float(ts_ms)
        quote.sequence = int(seq)
        quote.is_valid = 1
        
        # Step 3: Seqlock Write Complete (Increment to EVEN integer to signify stable data)
        quote.seqlock = current_seq + 2

    def read_all_quotes_for_symbol(self, symbol: str) -> Dict[str, Dict]:
        """
        Invoked by central microsecond engine to read current orderbooks across all venues lock-free.
        Enforces Seqlock verification: if a worker is mid-write (odd seqlock) or mutates memory mid-read, 
        discards the torn read and retries up to 3 times for pristine integrity.
        """
        results = {}
        symbol = symbol.upper()
        for ex in EXCHANGES:
            slot = self.slot_map.get((ex, symbol))
            if slot is None:
                continue
            offset = slot * self.struct_size
            quote = L2QuoteStruct.from_buffer(self.shm.buf, offset)
            
            if quote.is_valid != 1:
                continue

            # Seqlock Read Protocol (Torn Read Prevention)
            valid_read = False
            for _ in range(3):  # Max 3 rapid spin retries
                seq_start = quote.seqlock
                # If odd, write is active; spin briefly and retry
                if seq_start & 1 == 1:
                    continue
                
                # Copy values into safe memory variables
                bid_p = quote.bid_price
                bid_v = quote.bid_volume
                ask_p = quote.ask_price
                ask_v = quote.ask_volume
                ts_ms = quote.timestamp_ms
                seq_no = quote.sequence
                
                seq_end = quote.seqlock
                # If seqlock did not change during read and remains even, read was atomic!
                if seq_start == seq_end and (seq_end & 1 == 0):
                    valid_read = True
                    break
                else:
                    self.torn_reads_prevented += 1
            
            if valid_read:
                results[ex] = {
                    "bid": bid_p,
                    "bid_vol": bid_v,
                    "ask": ask_p,
                    "ask_vol": ask_v,
                    "timestamp_ms": ts_ms,
                    "sequence": seq_no
                }
        return results

    def invalidate_venue(self, exchange: str, symbol: str):
        """
        Marks an exchange quote as invalid (e.g., sequence disconnect or watchdog timeout).
        """
        slot = self.slot_map.get((exchange.lower(), symbol.upper()))
        if slot is None:
            return
        offset = slot * self.struct_size
        quote = L2QuoteStruct.from_buffer(self.shm.buf, offset)
        quote.is_valid = 0

    def close(self, unlink: bool = False):
        if self.shm is not None:
            try:
                self.shm.close()
                if unlink:
                    self.shm.unlink()
            except Exception:
                pass
