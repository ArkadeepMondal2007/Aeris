"""LIVE check: runs the real pipeline against the real Elexon API and prints the result.

This is separate from the unit tests, which never touch the network.
Run:  python live_check.py
"""
import asyncio
import json

from main import _convention, _rounded
from services.analytics import compute_metrics
from services.store import AnalysisStore
from settings import get_settings


async def main():
    settings = get_settings()
    analysis = await AnalysisStore(settings).get()
    print(_convention(settings))
    print(json.dumps(_rounded(compute_metrics(analysis.observations)), indent=2))
    print("data quality:", analysis.data_quality)
    sample = next((o for o in analysis.observations if o.error is not None), None)
    if sample:
        print(f"example: {sample.start:%d %b %H:%M}Z forecast {sample.forecast} (published {sample.published:%d %b %H:%M}Z) "
              f"actual {sample.actual} error {sample.error:+.0f}")


asyncio.run(main())
