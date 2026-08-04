import asyncio
import time
import websockets

async def bybit_ws_worker(pairs_dict, parse_json, dump_json, update_orderbook_callback):
    symbol_map = {v.upper(): k for k, v in pairs_dict.items()}
    url = "wss://stream.bybit.com/v5/public/spot"

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                args = [f"tickers.{v}" for v in pairs_dict.values()]
                sub_msg = {
                    "op": "subscribe",
                    "args": args
                }
                await ws.send(dump_json(sub_msg))
                print(f"[WebSocket] Subscribed to Bybit Multi-Pairs ({list(pairs_dict.keys())})")

                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    data = parse_json(message)
                    if 'data' in data and isinstance(data['data'], dict):
                        ticker = data['data']
                        raw_sym = ticker.get('symbol')
                        asset = symbol_map.get(raw_sym)
                        if asset and 'bid1Price' in ticker and 'ask1Price' in ticker:
                            bid = float(ticker['bid1Price'])
                            ask = float(ticker['ask1Price'])
                            update_orderbook_callback(asset, 'bybit', bid, ask, recv_ns)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Bybit WS Error] {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
