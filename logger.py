import os
import csv
import datetime
from typing import Dict, List, Optional

class ArbitrageLogger:
    """
    Production Paper Trading & Performance Ledger Engine.
    
    Generates two live-updating documents:
    1. `paper_trading_ledger.csv` - Granular, row-by-row transaction ledger for every paper-executed trade.
    2. `PAPER_RETURNS_REPORT.md` - Formatted institutional executive report tracking cumulative paper ROI,
       win rate, total trading volume, fee deductions, and asset breakdowns.
    """
    def __init__(self, log_path: Optional[str] = None, initial_capital_usdt: float = 21000.0, enabled: bool = True):
        self.enabled = enabled
        self.initial_capital = initial_capital_usdt
        self.current_balance = initial_capital_usdt
        self.cumulative_pnl = 0.0
        self.total_volume = 0.0
        self.total_fees = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.csv_path = log_path or os.path.join(base_dir, "paper_trading_ledger.csv")
        self.md_report_path = os.path.join(base_dir, "PAPER_RETURNS_REPORT.md")
        
        self.asset_stats: Dict[str, Dict] = {}
        self.venue_stats: Dict[str, Dict] = {}
        self.recent_trades: List[Dict] = []
        
        if self.enabled:
            self._init_csv_ledger()
            self.generate_markdown_report()

    def _init_csv_ledger(self):
        if not os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "trade_id",
                        "timestamp_utc",
                        "asset",
                        "buy_exchange",
                        "buy_price",
                        "sell_exchange",
                        "sell_price",
                        "quantity",
                        "notional_usd",
                        "gross_spread_per_unit",
                        "gross_profit_usd",
                        "total_fees_usd",
                        "net_profit_usd",
                        "cumulative_net_pnl_usd",
                        "paper_balance_usd",
                        "eval_latency_micros"
                    ])
            except Exception as e:
                print(f"[Logger Error] Failed to initialize CSV ledger: {e}")

    def log_paper_trade(
        self,
        asset: str,
        buy_ex: str,
        buy_price: float,
        sell_ex: str,
        sell_price: float,
        quantity: float,
        gross_spread_per_unit: float,
        net_profit_per_unit: float,
        fee_buy_rate: float,
        fee_sell_rate: float,
        eval_micros: float
    ):
        """Records a fully reconciled paper trade and updates paper performance documents."""
        if not self.enabled:
            return
            
        self.total_trades += 1
        notional_usd = buy_price * quantity
        gross_profit = gross_spread_per_unit * quantity
        fee_buy_usd = notional_usd * fee_buy_rate
        fee_sell_usd = (sell_price * quantity) * fee_sell_rate
        total_fees = fee_buy_usd + fee_sell_usd
        net_profit_usd = net_profit_per_unit * quantity
        
        self.cumulative_pnl += net_profit_usd
        self.current_balance = self.initial_capital + self.cumulative_pnl
        self.total_volume += notional_usd
        self.total_fees += total_fees
        
        if net_profit_usd > 0:
            self.winning_trades += 1
            
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        trade_id = f"PT-{self.total_trades:05d}"
        
        # Track Asset Metrics
        if asset not in self.asset_stats:
            self.asset_stats[asset] = {"trades": 0, "net_pnl": 0.0, "volume": 0.0}
        self.asset_stats[asset]["trades"] += 1
        self.asset_stats[asset]["net_pnl"] += net_profit_usd
        self.asset_stats[asset]["volume"] += notional_usd
        
        # Track Venue Pair Metrics
        pair_key = f"{buy_ex.upper()} -> {sell_ex.upper()}"
        if pair_key not in self.venue_stats:
            self.venue_stats[pair_key] = {"trades": 0, "net_pnl": 0.0}
        self.venue_stats[pair_key]["trades"] += 1
        self.venue_stats[pair_key]["net_pnl"] += net_profit_usd
        
        trade_record = {
            "trade_id": trade_id,
            "timestamp": now_str,
            "asset": asset,
            "buy_ex": buy_ex.upper(),
            "buy_price": buy_price,
            "sell_ex": sell_ex.upper(),
            "sell_price": sell_price,
            "quantity": quantity,
            "notional": notional_usd,
            "gross_profit": gross_profit,
            "fees": total_fees,
            "net_profit": net_profit_usd,
            "cum_pnl": self.cumulative_pnl,
            "balance": self.current_balance,
            "latency": eval_micros
        }
        
        self.recent_trades.append(trade_record)
        if len(self.recent_trades) > 20:
            self.recent_trades.pop(0)
            
        # Append to CSV
        try:
            with open(self.csv_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade_id,
                    now_str,
                    asset,
                    buy_ex.upper(),
                    f"{buy_price:.4f}",
                    sell_ex.upper(),
                    f"{sell_price:.4f}",
                    f"{quantity:.4f}",
                    f"{notional_usd:.2f}",
                    f"{gross_spread_per_unit:.4f}",
                    f"{gross_profit:.4f}",
                    f"{total_fees:.4f}",
                    f"{net_profit_usd:.4f}",
                    f"{self.cumulative_pnl:.4f}",
                    f"{self.current_balance:.4f}",
                    f"{eval_micros:.2f}"
                ])
        except Exception as e:
            print(f"[Logger Error] Failed to write trade to CSV: {e}")
            
        # Update Markdown Report
        self.generate_markdown_report()

    # Backwards compatibility alias
    def log_opportunity(self, buy_ex, buy_ask, sell_ex, sell_bid, gross_spread, net_profit, eval_micros):
        pass

    def generate_markdown_report(self):
        """Generates executive PAPER_RETURNS_REPORT.md summarizing paper trading performance."""
        if not self.enabled:
            return
            
        roi_pct = ((self.current_balance - self.initial_capital) / self.initial_capital) * 100.0 if self.initial_capital > 0 else 0.0
        win_rate = (self.winning_trades / self.total_trades * 100.0) if self.total_trades > 0 else 100.0
        avg_profit = (self.cumulative_pnl / self.total_trades) if self.total_trades > 0 else 0.0
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        content = f"""# 📈 Quantitative Crypto Arbitrage — Paper Trading Returns Report

*Last Updated: **{now_str}***  
*Mode: **Zero-Risk Live Shadow Testing (Public Level-2 WebSocket Feeds)***

---

## 🏛️ Executive Performance Summary

| Metric | Current Value | Description |
| :--- | :--- | :--- |
| **Initial Paper Capital** | **${self.initial_capital:,.2f} USDT** | Starting allocated virtual capital |
| **Current Portfolio Balance** | **${self.current_balance:,.2f} USDT** | Balance including net realized paper returns |
| **Cumulative Net Return (PnL)** | **{'+' if self.cumulative_pnl >= 0 else ''}${self.cumulative_pnl:,.4f} USDT** | Realized profit after all exchange taker fees |
| **Paper ROI (%)** | **{'+' if roi_pct >= 0 else ''}{roi_pct:.3f}%** | Percentage return on allocated capital |
| **Total Trades Executed** | **{self.total_trades:,}** | Total verified non-ghost arbitrage fills |
| **Win Rate** | **{win_rate:.1f}%** ({self.winning_trades}/{self.total_trades if self.total_trades > 0 else 1}) | Trades with positive net return after fees |
| **Total Notional Traded** | **${self.total_volume:,.2f} USDT** | Cumulative traded transaction volume |
| **Total Exchange Fees Deducted** | **${self.total_fees:,.4f} USDT** | Modeled exchange taker/maker trading fees |
| **Average Profit per Trade** | **${avg_profit:.4f} USDT** | Net profit margin per executed arbitrage leg |

---

## 📊 Performance by Asset Pair

| Asset | Total Trades | Total Volume Traded | Realized Net PnL |
| :--- | :--- | :--- | :--- |
"""
        if self.asset_stats:
            for ast, stats in self.asset_stats.items():
                content += f"| **{ast}** | {stats['trades']} | ${stats['volume']:,.2f} USDT | {'+' if stats['net_pnl'] >= 0 else ''}${stats['net_pnl']:,.4f} USDT |\n"
        else:
            content += "| *Scanning...* | 0 | $0.00 USDT | $0.0000 USDT |\n"

        content += """
---

## 🌐 Performance by Exchange Routing

| Routing Path | Total Trades | Realized Net PnL |
| :--- | :--- | :--- |
"""
        if self.venue_stats:
            for route, stats in self.venue_stats.items():
                content += f"| **{route}** | {stats['trades']} | {'+' if stats['net_pnl'] >= 0 else ''}${stats['net_pnl']:,.4f} USDT |\n"
        else:
            content += "| *Scanning regional clusters...* | 0 | $0.0000 USDT |\n"

        content += """
---

## 📜 Recent Trade Ledger (Last 20 Executions)

| Trade ID | Time (UTC) | Asset | Buy Venue @ Price | Sell Venue @ Price | Size (Units) | Net Profit | Cum. PnL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        if self.recent_trades:
            for t in reversed(self.recent_trades):
                content += f"| `{t['trade_id']}` | {t['timestamp']} | **{t['asset']}** | {t['buy_ex']} @ ${t['buy_price']:,.2f} | {t['sell_ex']} @ ${t['sell_price']:,.2f} | {t['quantity']:.4f} | **+${t['net_profit']:.4f}** | ${t['cum_pnl']:.4f} |\n"
        else:
            content += "| *No trades executed yet* | — | — | — | — | — | — | — |\n"

        content += f"""
---
*📄 Raw transaction records are appended in real-time to [`paper_trading_ledger.csv`](file://{self.csv_path})*
"""
        try:
            with open(self.md_report_path, "w", encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"[Logger Error] Failed to write Markdown report: {e}")
