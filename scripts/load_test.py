"""Burst test (spec 019 item 5): N concurrent GET /v1/countries/{iso2} while /v1/health is polled.

Run against a LOCAL server started with a small pool that mimics the Supabase pooler, e.g.
  DB_POOL_SIZE=3 DB_MAX_OVERFLOW=0 PYTHONPATH=src .venv/Scripts/python.exe -m uvicorn atlas_api.main:app --port 8765
  .venv/Scripts/python.exe scripts/load_test.py http://127.0.0.1:8765 100
Pass = every request finishes (200 or a fast 503) and health keeps answering in < 2 s.
"""
import asyncio
import collections
import sys
import time

import httpx


async def main(base: str, n: int) -> int:
    limits = httpx.Limits(max_connections=None)  # the burst must not queue on the client side
    async with (httpx.AsyncClient(base_url=base, timeout=60, limits=limits) as c,
                httpx.AsyncClient(base_url=base, timeout=60) as hc):  # own connection for health
        isos = [x["iso2"] for x in (await c.get("/v1/countries")).json()["items"]]
        done = asyncio.Event()
        health: list[float] = []

        async def poll_health() -> None:
            while not done.is_set():
                t = time.perf_counter()
                await hc.get("/v1/health")
                health.append(time.perf_counter() - t)
                await asyncio.sleep(0.2)

        async def one(iso: str) -> tuple[int, float]:
            t = time.perf_counter()
            r = await c.get(f"/v1/countries/{iso}")
            return r.status_code, time.perf_counter() - t

        poller = asyncio.create_task(poll_health())
        t0 = time.perf_counter()
        results = await asyncio.gather(*(one(isos[i % len(isos)]) for i in range(n)))
        total = time.perf_counter() - t0
        done.set()
        await poller
    codes = collections.Counter(s for s, _ in results)
    slowest = max(d for _, d in results)
    print(f"{n} concurrent GETs in {total:.1f}s: {dict(codes)}; slowest {slowest:.1f}s")
    print(f"health: {len(health)} checks during the burst, slowest {max(health):.2f}s")
    ok = set(codes) <= {200, 503} and max(health) < 2
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 100)))
