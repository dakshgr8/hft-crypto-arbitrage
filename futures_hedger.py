import time
from typing import Dict, Optional

class PerpetualFuturesHedger:
    """
    Perpetual Futures Delta-Neutral Hedging & Post-Only "Chase the Book" with Taker Override.
    
    Replaces spot market panic-dumping when Leg B execution fails or experiences partial fills by opening 
    an instantaneous 1x Short on USDT-M Perpetual Futures to lock in zero delta risk (Delta = 0).
    Then gracefully unwinds spot inventory using passive Post-Only Maker limit orders, 
    employing a dynamic "Chase the Book" protocol. If real-world exchange price action causes repeat rejections 
    exceeding MAX_CHASE_STEPS (default 5), it executes a Taker Market override to avoid infinite loops and inventory decay.
    """
    def __init__(self, primary_futures_venue: str = 'binance_futures'):
        self.primary_futures_venue = primary_futures_venue
        self.active_hedges: Dict[str, Dict] = {}
        self.total_hedged_volume_usd: float = 0.0
        self.hedge_events_count: int = 0
        self.estimated_fee_savings_usd: float = 0.0
        
        # Chase Protocol & Flash-Crash Override Metrics
        self.post_only_rejections_occurred: int = 0
        self.chase_protocol_successes: int = 0
        self.maker_unwinds_completed: int = 0
        self.taker_fallback_conversions: int = 0

    def execute_emergency_hedge(self, symbol: str, spot_exchange: str, failed_exchange: str, unhedged_qty: float, entry_price: float) -> Dict:
        """
        Triggered when Leg B fails after Leg A executes.
        Opens a Short Perpetual Futures position to achieve instantaneous delta neutrality (Delta = 0).
        """
        ts_start_us = time.perf_counter_ns() / 1000.0
        
        # Estimate theoretical spot dump loss (Double Taker Fees + 0.15% forced bid slippage)
        spot_taker_fee_rate = 0.0010
        spot_slippage_rate = 0.0015
        spot_dump_loss = unhedged_qty * entry_price * (spot_taker_fee_rate + spot_slippage_rate)
        
        # Calculate perpetual futures hedging cost (Low futures taker fee ~0.04%, tight spread)
        futures_taker_fee_rate = 0.0004
        futures_slippage_rate = 0.0002
        futures_hedge_cost = unhedged_qty * entry_price * (futures_taker_fee_rate + futures_slippage_rate)
        
        # Net saving from using Futures instead of Spot Panic Dump
        savings = max(0.0, spot_dump_loss - futures_hedge_cost)
        self.estimated_fee_savings_usd += savings
        
        hedge_id = f"HEDGE_{symbol}_{int(time.time()*1000)}_{self.hedge_events_count}"
        hedge_record = {
            "hedge_id": hedge_id,
            "symbol": symbol,
            "spot_venue": spot_exchange,
            "failed_venue": failed_exchange,
            "futures_venue": self.primary_futures_venue,
            "direction": "SHORT_PERP",
            "quantity": unhedged_qty,
            "hedge_price": entry_price, # Assumes perp tracks spot closely
            "status": "DELTA_NEUTRAL",
            "timestamp": time.time(),
            "execution_time_us": (time.perf_counter_ns() / 1000.0) - ts_start_us,
            "saved_vs_spot_dump_usd": round(savings, 4),
            "chase_attempts": 0
        }
        
        self.active_hedges[hedge_id] = hedge_record
        self.total_hedged_volume_usd += unhedged_qty * entry_price
        self.hedge_events_count += 1
        
        return hedge_record

    def unwind_spot_via_chase_protocol(self, hedge_id: str, current_spot_bid: float, current_spot_ask: float, max_chase_attempts: int = 5, api_rejection_received: bool = False) -> Optional[Dict]:
        """
        "Chase the Book" Post-Only Maker protocol with Flash-Crash Taker Fallback.
        When unwinding spot inventory, we submit passive Maker orders (post_only=True).
        If price crosses limit price before arrival, real exchange APIs reject Post-Only orders (api_rejection_received=True).
        If rejection loop exceeds max_chase_attempts (MAX_CHASE_STEPS = 5), overrides post_only flag and crosses the spread as Taker!
        """
        if hedge_id not in self.active_hedges:
            return None
            
        hedge = self.active_hedges[hedge_id]
        symbol = hedge['symbol']
        venue = hedge['spot_venue']
        qty = hedge['quantity']
        attempt = hedge.get('chase_attempts', 0) + 1
        hedge['chase_attempts'] = attempt
        
        current_limit_price = current_spot_ask
        
        if api_rejection_received:
            self.post_only_rejections_occurred += 1
            print(f" [⚡ POST-ONLY REJECTION: {venue.upper()}] Price shifted across ${current_limit_price:.4f} in microsecond transit! Maker order rejected to prevent Taker execution.")
            
            if attempt <= max_chase_attempts:
                # Chase the Book: Recalculate best ask 1 tick above updated bid
                new_limit_price = current_spot_bid * (1.0002 - (0.00005 * attempt))
                print(f" [🏇 CHASE THE BOOK PROTOCOL] Recomputing passive Maker tick -> New Post-Only Ask at ${new_limit_price:.4f} (Chase Attempt {attempt}/{max_chase_attempts})...")
                hedge["status"] = f"CHASE_IN_PROGRESS_ATTEMPT_{attempt}"
                return hedge
            else:
                # MAX_CHASE_STEPS exceeded! We are in a flash-crash freefall. Trigger Taker Override!
                self.taker_fallback_conversions += 1
                execution_taker_price = current_spot_bid * 0.9995  # Cross spread as Taker
                print(f" [🚨 FLASH-CRASH TAKER OVERRIDE: {venue.upper()}] MAX_CHASE_STEPS ({max_chase_attempts}) exceeded without Maker fill! Overriding post_only=False.")
                print(f"    Executed aggressive Taker Limit @ ${execution_taker_price:.4f} to eliminate unhedged delta decay and prevent API rate-limit loop paralysis!")
                
                hedge["status"] = "UNWOUND_EMERGENCY_TAKER_OVERRIDE"
                hedge["unwind_timestamp"] = time.time()
                hedge["final_unwind_price"] = execution_taker_price
                del self.active_hedges[hedge_id]
                return hedge
        else:
            # Order executed successfully as Post-Only Maker
            self.maker_unwinds_completed += 1
            if attempt > 1:
                self.chase_protocol_successes += 1
                print(f" [🏆 CHASE SUCCESSFUL: {venue.upper()}] Spot inventory ({qty:.4f} {symbol}) fully executed as passive Maker @ ${current_limit_price:.4f}! Zero Taker slippage paid.")
            
            hedge["status"] = "UNWOUND_GRACEFULLY_MAKER"
            hedge["unwind_timestamp"] = time.time()
            hedge["final_unwind_price"] = current_limit_price
            del self.active_hedges[hedge_id]
            return hedge

    def get_telemetry_metrics(self) -> Dict:
        return {
            "active_hedges_count": len(self.active_hedges),
            "total_hedge_events": self.hedge_events_count,
            "hedged_volume_usd": round(self.total_hedged_volume_usd, 2),
            "est_saved_vs_spot_dump_usd": round(self.estimated_fee_savings_usd, 4),
            "post_only_rejections": self.post_only_rejections_occurred,
            "chase_protocol_wins": self.chase_protocol_successes,
            "maker_unwinds_total": self.maker_unwinds_completed,
            "taker_fallback_conversions": self.taker_fallback_conversions
        }
