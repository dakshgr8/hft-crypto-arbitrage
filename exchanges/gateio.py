import asyncio
import time
import websockets

async def gateio_ws_worker(pairs_dict, parse_json, dump_json, update_orderbook_callback):
    pair_map = {v: k for k, v in pairs_dict.items()}
    url = "wss://api.gateio.ws/ws/v4/"

    while True:
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
                sub_msg = {
                    "time": int(time.time()),
                    "channel": "spot.tickers",
                    "event": "subscribe",
                    "payload": list(pairs_dict.values())
                }
                await ws.send(dump_json(sub_msg))
                print(f"[WebSocket] Subscribed to Gate.io Multi-Pairs ({list(pairs_dict.keys())})")

                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    data = parse_json(message)
                    if data.get('event') == 'update' and 'result' in data:
                        res = data['result']
                        cp = res.get('currency_pair')
                        asset = pair_map.get(cp)
                        if asset and 'highest_bid' in res and 'lowest_ask' in res:
                            bid = float(res['highest_bid'])
                            ask = float(res['lowest_ask'])
                            server_ts = res.get('t') or (time.time() * 1000.0)
                            if bid > 0 and ask > 0:
                                update_orderbook_callback(asset, 'gateio', bid, ask, recv_ns, server_ts)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Gate.io WS Error] {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
