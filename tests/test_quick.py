import asyncio
import pytest
from src.startup_wiring import bootstrap_jarvis

@pytest.mark.asyncio
async def test():
    print("Starting bootstrap...")
    result = await bootstrap_jarvis(
        start_autonomous=False,  # Skip autonomous loop to avoid timeout
        start_gpu_guardian=False,
        start_trading_sentinel=False
    )
    
    print(f"\n{'='*60}")
    print(f"Bootstrap Result:")
    print(f"  Success: {result['success']}")
    print(f"  Steps: {result['steps_ok']}/{result['steps_total']}")
    print(f"  Duration: {result['duration_ms']:.1f}ms")
    print(f"{'='*60}")
    
    if result['errors']:
        print(f"\nErrors: {len(result['errors'])}")
        for e in result['errors']:
            print(f"  - {e}")
    
    # Check scheduler jobs
    from src.database import get_connection
    jobs = get_connection().execute('SELECT name FROM scheduler_jobs').fetchall()
    print(f"\nScheduler jobs created: {len(jobs)}")
    for job in jobs:
        print(f"  - {job[0]}")
    
    return result

if __name__ == '__main__':
    asyncio.run(test())

