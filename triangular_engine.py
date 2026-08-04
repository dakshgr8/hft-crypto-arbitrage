"""
Triangular Arbitrage Engine
Calculates single-exchange 3-pair loop opportunities (e.g., USDT -> BTC -> ETH -> USDT).
Eliminates cross-exchange transfer delays and multi-account capital fragmentation.
"""
import time

class TriangularEngine:
    def __init__(self, fee_rate=0.0010): # 0.10% per trade on Binance
        self.fee_rate = fee_rate
        self.net_fee_factor = (1.0 - self.fee_rate) ** 3 # Fee factor for 3 trades

    def evaluate_triangular_loop(self, start_amount_usdt, usdt_btc_ask, btc_eth_ask, eth_usdt_bid):
        """
        Loop: USDT -> BTC (Buy Ask) -> ETH (Buy Ask) -> USDT (Sell Bid)
        usdt_btc_ask: BTC price in USDT (Ask)
        btc_eth_ask: ETH price in BTC (Ask)
        eth_usdt_bid: ETH price in USDT (Bid)
        """
        if usdt_btc_ask <= 0 or btc_eth_ask <= 0 or eth_usdt_bid <= 0:
            return 0.0, 0.0, 0.0

        t_start = time.perf_counter_ns()

        # Step 1: Buy BTC with USDT
        btc_amount = (start_amount_usdt / usdt_btc_ask) * (1.0 - self.fee_rate)

        # Step 2: Buy ETH with BTC
        eth_amount = (btc_amount / btc_eth_ask) * (1.0 - self.fee_rate)

        # Step 3: Sell ETH for USDT
        final_usdt = (eth_amount * eth_usdt_bid) * (1.0 - self.fee_rate)

        net_profit_usdt = final_usdt - start_amount_usdt
        roi_pct = (net_profit_usdt / start_amount_usdt) * 100.0

        t_end = time.perf_counter_ns()
        eval_micros = (t_end - t_start) / 1000.0

        return net_profit_usdt, roi_pct, eval_micros
