"""
Level 2 Order Book Depth & Slippage Engine
Calculates Volume-Weighted Average Price (VWAP) for specified trade sizes ($1k, $5k, $10k)
to prevent trading into thin orderbook levels.
"""

class DepthEngine:
    @staticmethod
    def calculate_buy_vwap(asks, target_size_usd):
        """
        Calculates VWAP to BUY target_size_usd worth of asset from asks.
        asks: list of [price, size]
        Returns: (vwap_price, total_crypto_filled, slippage_pct)
        """
        if not asks:
            return 0.0, 0.0, 0.0

        remaining_usd = target_size_usd
        total_crypto = 0.0
        spent_usd = 0.0
        best_ask = float(asks[0][0])

        for level in asks:
            price = float(level[0])
            qty = float(level[1])
            level_usd = price * qty

            if level_usd >= remaining_usd:
                needed_qty = remaining_usd / price
                total_crypto += needed_qty
                spent_usd += remaining_usd
                remaining_usd = 0.0
                break
            else:
                total_crypto += qty
                spent_usd += level_usd
                remaining_usd -= level_usd

        if remaining_usd > 0 or total_crypto == 0:
            # Insufficient orderbook depth for target trade size
            return 0.0, 0.0, 0.0

        vwap_price = spent_usd / total_crypto
        slippage_pct = ((vwap_price - best_ask) / best_ask) * 100.0
        return vwap_price, total_crypto, slippage_pct

    @staticmethod
    def calculate_sell_vwap(bids, target_crypto_amount):
        """
        Calculates VWAP to SELL target_crypto_amount to bids.
        bids: list of [price, size]
        Returns: (vwap_price, total_usd_received, slippage_pct)
        """
        if not bids:
            return 0.0, 0.0, 0.0

        remaining_crypto = target_crypto_amount
        total_usd = 0.0
        best_bid = float(bids[0][0])

        for level in bids:
            price = float(level[0])
            qty = float(level[1])

            if qty >= remaining_crypto:
                total_usd += remaining_crypto * price
                remaining_crypto = 0.0
                break
            else:
                total_usd += qty * price
                remaining_crypto -= qty

        if remaining_crypto > 0:
            # Insufficient bid depth
            return 0.0, 0.0, 0.0

        vwap_price = total_usd / target_crypto_amount
        slippage_pct = ((best_bid - vwap_price) / best_bid) * 100.0
        return vwap_price, total_usd, slippage_pct
