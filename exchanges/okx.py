import asyncio
import time
import websockets

async def okx_ws_worker(pairs_dict, parse_json, dump_json, update_orderbook_callback):
    inst_map = {v: k for k, v in pairs_dict.items()}
    url = "wss://ws.okx.com:8443/ws/v5/public"

    while True:
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
                args = [{"channel": "tickers", "instId": v} for v in pairs_dict.values()]
                sub_msg = {
                    "op": "subscribe",
                    "args": args
                }
                await ws.send(dump_json(sub_msg))
                print(f"[WebSocket] Subscribed to OKX Multi-Pairs ({list(pairs_dict.keys())})")

                async for message in ws:
                    recv_ns = time.perf_counter_ns()
                    data = parse_json(message)
                    if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                        ticker = data['data'][0]
                        inst_id = ticker.get('instId')
                        asset = inst_map.get(inst_id)
                        if asset and 'bidPx' in ticker and 'askPx' in ticker:
                            bid = float(ticker['bidPx'])
                            ask = float(ticker['askPx'])
                            server_ts = ticker.get('ts')
                            if bid > 0 and ask > 0:
                                update_orderbook_callback(asset, 'okx', bid, ask, recv_ns, server_ts)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[OKX WS Error] {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
