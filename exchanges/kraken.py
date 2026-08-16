import asyncio
import time
import websockets

async def kraken_ws_worker(pairs_dict, parse_json, dump_json, update_orderbook_callback):
    # Mapping kraken pair name to asset (e.g. XBT/USDT -> BTC)
    pair_map = {v: k for k, v in pairs_dict.items()}
    url = "wss://ws.kraken.com"

    while True:
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
                sub_msg = {
                    "event": "subscribe",
                    "pair": list(pairs_dict.values()),
                    "subscription": {"name": "ticker"}
                }
                await ws.send(dump_json(sub_msg))
                print(f"[WebSocket] Subscribed to Kraken Multi-Pairs ({list(pairs_dict.keys())})")

                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    data = parse_json(message)
                    if isinstance(data, list) and len(data) >= 4:
                        raw_pair = data[3]
                        asset = pair_map.get(raw_pair)
                        ticker = data[1]
                        if asset and 'b' in ticker and 'a' in ticker:
                            bid = float(ticker['b'][0])
                            ask = float(ticker['a'][0])
                            if bid > 0 and ask > 0:
                                update_orderbook_callback(asset, 'kraken', bid, ask, recv_ns, time.time() * 1000.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Kraken WS Error] {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
