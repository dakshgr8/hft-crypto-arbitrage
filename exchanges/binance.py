import asyncio
import time
import websockets

async def binance_ws_worker(pairs_dict, parse_json, update_orderbook_callback):
    # Reverse mapping from Binance ticker symbol to asset name (e.g. BTCUSDT -> BTC)
    asset_map = {v.upper(): k for k, v in pairs_dict.items()}
    streams = "/".join([f"{v.lower()}@bookTicker" for v in pairs_dict.values()])
    
    # Support multiple global & US mirror endpoints for seamless cloud hosting
    endpoints = [
        f"wss://stream.binance.com:9443/stream?streams={streams}",
        f"wss://stream.binance.us:9443/stream?streams={streams}",
        f"wss://data-stream.binance.vision/stream?streams={streams}"
    ]
    
    ep_idx = 0
    while True:
        url = endpoints[ep_idx % len(endpoints)]
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                print(f"[WebSocket] Connected to Binance Multi-Pair Stream ({url.split('/')[2]})")
                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    payload = parse_json(message)
                    data = payload.get('data', payload)
                    raw_symbol = data.get('s')
                    asset = asset_map.get(raw_symbol)
                    
                    if asset and 'b' in data and 'a' in data:
                        bid = float(data['b'])
                        ask = float(data['a'])
                        if bid > 0 and ask > 0:
                            update_orderbook_callback(asset, 'binance', bid, ask, recv_ns, time.time() * 1000.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Binance WS Error on {url.split('/')[2]}] {e}. Trying fallback endpoint in 3s...")
            ep_idx += 1
            await asyncio.sleep(3)
