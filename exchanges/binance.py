import asyncio
import time
import websockets

async def binance_ws_worker(pairs_dict, parse_json, update_orderbook_callback):
    # Reverse mapping from Binance ticker symbol to asset name (e.g. BTCUSDT -> BTC)
    asset_map = {v.upper(): k for k, v in pairs_dict.items()}
    streams = "/".join([f"{v.lower()}@bookTicker" for v in pairs_dict.values()])
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                print(f"[WebSocket] Connected to Binance Multi-Pair Stream")
                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    payload = parse_json(message)
                    data = payload.get('data', payload)
                    raw_symbol = data.get('s')
                    asset = asset_map.get(raw_symbol)
                    
                    if asset and 'b' in data and 'a' in data:
                        bid = float(data['b'])
                        ask = float(data['a'])
                        update_orderbook_callback(asset, 'binance', bid, ask, recv_ns)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Binance WS Error] {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
