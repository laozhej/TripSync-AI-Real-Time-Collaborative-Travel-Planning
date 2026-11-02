"""Synthetic direct-model diagnostic; no deadline changes in the application."""
import asyncio
import json
from pathlib import Path
import time
import httpx
from app.datasets.schema import Dataset
from app.concierge.rag import answer_from_model


async def main():
    dataset = Dataset.model_validate_json(Path('data/destinations/bengaluru.json').read_text())
    choices = [{'venue': v, 'venueId': v.sourceId, 'currency': 'INR'} for v in dataset.venues if v.category == 'food'][:2]
    metrics = {}
    async def capture(response):
        await response.aread()
        body = response.json()
        metrics.update({k: body[k] for k in ('total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration') if k in body})
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=60, trust_env=False,
            event_hooks={'response': [capture]}) as client:
        t = time.perf_counter()
        result = await answer_from_model(choices, 'Find synthetic vegetarian food', 1, client, timeout=60)
        metrics.update(elapsedMs=(time.perf_counter()-t)*1000, status=result['status'], diagnosticOnlyDeadlineSeconds=60)
    out = Path('evidence/performance/model-diagnostic.json')
    out.write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print(json.dumps(metrics, indent=2))


asyncio.run(main())
