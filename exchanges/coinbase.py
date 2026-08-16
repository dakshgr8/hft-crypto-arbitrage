import asyncio
import time
import websockets

async def coinbase_ws_worker(pairs_dict, parse_json, dump_json, update_orderbook_callback):
    product_map = {v: k for k, v in pairs_dict.items()}
    url = "wss://ws-feed.exchange.coinbase.com"

    while True:
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
                sub_msg = {
                    "type": "subscribe",
                    "product_ids": list(pairs_dict.values()),
                    "channels": ["ticker", "heartbeat"]
                }
                await ws.send(dump_json(sub_msg))
                print(f"[WebSocket] Subscribed to Coinbase Multi-Pairs ({list(pairs_dict.keys())})")

                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    data = parse_json(message)
                    msg_type = data.get('type')
                    if msg_type == 'ticker' and 'best_bid' in data and 'best_ask' in data:
                        prod_id = data.get('product_id')
                        asset = product_map.get(prod_id)
                        if asset:
                            bid = float(data['best_bid'])
                            ask = float(data['best_ask'])
                            server_ts = data.get('time')
                            if bid > 0 and ask > 0:
                                update_orderbook_callback(asset, 'coinbase', bid, ask, recv_ns, server_ts)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Coinbase WS Error] {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
