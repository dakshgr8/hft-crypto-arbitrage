import os
import csv
import datetime

class ArbitrageLogger:
    def __init__(self, log_path, enabled=True):
        self.log_path = log_path
        self.enabled = enabled
        if self.enabled and not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_utc", 
                    "buy_exchange", 
                    "buy_ask_price", 
                    "sell_exchange", 
                    "sell_bid_price", 
                    "gross_spread", 
                    "net_profit_usdt", 
                    "eval_latency_micros"
                ])

    def log_opportunity(self, buy_ex, buy_ask, sell_ex, sell_bid, gross_spread, net_profit, eval_micros):
        if not self.enabled:
            return
        now_str = datetime.datetime.utcnow().isoformat()
        try:
            with open(self.log_path, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    now_str,
                    buy_ex,
                    f"{buy_ask:.2f}",
                    sell_ex,
                    f"{sell_bid:.2f}",
                    f"{gross_spread:.2f}",
                    f"{net_profit:.2f}",
                    f"{eval_micros:.2f}"
                ])
        except Exception as e:
            print(f"[Logger Error] Failed to write log: {e}")
