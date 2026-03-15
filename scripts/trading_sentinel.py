
import asyncio
import httpx
import logging
from src.consensus import consensus_engine

# Configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
ALERT_THRESHOLD = 1.5 # % variation for deep analysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s [TRADING-V2.3] %(message)s')

class TradingSentinelV2:
    """Blueprint Etoile Trading v2.3 - Multi-IA Consensus."""

    def __init__(self):
        self.prices = {}

    async def get_consensus_signal(self, symbol, price, change):
        prompt = f"Analyse technique éclair pour {symbol} à ${price} ({change:+.2f}%). Faut-il prendre une position long/short 10x ?"
        # Sollicite le cluster via le moteur de consensus
        res = await consensus_engine.run_consensus(prompt, ["M1", "M2", "OL1", "GEMINI"])
        return res

    async def check_market(self):
        url = "https://api.mexc.com/api/v3/ticker/price"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                data = resp.json()
                current_data = {item['symbol']: float(item['price']) for item in data if item['symbol'] in SYMBOLS}
                
                for symbol, price in current_data.items():
                    if symbol in self.prices:
                        change = ((price - self.prices[symbol]) / self.prices[symbol]) * 100
                        if abs(change) >= ALERT_THRESHOLD:
                            logging.warning(f"🚀 Movement detected: {symbol} {change:.2f}%")
                            signal = await self.get_consensus_signal(symbol, price, change)
                            logging.info(f"💎 CONSENSUS SIGNAL: {signal['final_answer']}")
                    self.prices[symbol] = price
        except Exception as e:
            logging.error(f"Market check error: {e}")

    async def run(self):
        logging.info("Trading Sentinel v2.3 ACTIVE (Consensus Mode).")
        while True:
            await self.check_market()
            await asyncio.sleep(60)

if __name__ == "__main__":
    sentinel = TradingSentinelV2()
    asyncio.run(sentinel.run())
