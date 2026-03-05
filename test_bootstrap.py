import asyncio
from src.startup_wiring import bootstrap_jarvis

async def test():
    result = await bootstrap_jarvis()
    print(f"\nBootstrap Result:")
    print(f"  Success: {result['success']}")
    print(f"  Steps: {result['steps_ok']}/{result['steps_total']}")
    print(f"  Duration: {result['duration_ms']}ms")
    if result['errors']:
        print(f"\nErrors: {len(result['errors'])}")
        for e in result['errors'][:3]:
            print(f"  - {e}")
    return result

if __name__ == '__main__':
    asyncio.run(test())

