# Read This — LLM Market Forecaster Overview

*A plain-English guide so you can explain this project in an interview, a demo or a talk.*

## In one sentence
Every morning it reads crypto price data, asks a local AI for a forecast, writes a plain-English report, and the next day checks whether it was right.

## The problem it solves
Plenty of tools make predictions. Almost none keep score. Without a track record you can't tell a smart forecaster from a lucky one.

## How it works, step by step
1. On a daily schedule, it downloads recent price history (candles) for each coin from public exchange APIs. If Kraken is down it falls back to Coinbase, then CoinGecko.
2. It squeezes hundreds of raw numbers into a short, structured summary covering trend, volatility and recent highs and lows, so the AI gets signal instead of noise.
3. A local AI model reads the summary and returns a call (bullish, bearish or neutral) with a confidence score and its reasoning.
4. Every forecast goes into a small database and into a readable daily report.
5. The next day, it compares each call against what the price actually did and records a hit or a miss. The dashboard shows accuracy over time.

See the diagram: [docs/workflow.png](docs/workflow.png)

## The everyday comparison
A weather forecaster who has to write tomorrow's forecast on the whiteboard and then gets graded every morning in front of everyone.

## Why it works
AI models handle short, well-organised summaries far better than raw tables of numbers. Compressing the data first is what makes the forecast sensible. Grading every prediction against reality turns it from an opinion generator into something you can measure.

## What makes it impressive
- Built-in self-evaluation, which most AI demos skip entirely.
- Data-source failover, so one exchange going down doesn't break the run.
- Picks a model size that fits the graphics card it finds.
- No keys, no accounts, no trading. Safe to run and share.

## Your 30-second pitch
> "This is a scheduled AI pipeline that makes daily crypto forecasts with a local model, and the key part is that it grades itself. Each forecast is stored, then checked against what actually happened, so you get a real accuracy record instead of confident guesses. The same pattern works for any forecasting problem."

## Questions you'll likely get, and good answers
**Q: Is it accurate?**  
A: That's exactly what it's built to measure. The point is the accountability loop, not claiming the AI can beat the market.

**Q: Why compress the data?**  
A: Models reason better over a clear summary than over raw numbers, and it keeps each run fast and cheap.

**Q: Where else does this pattern apply?**  
A: Sales forecasts, demand planning, ticket volume. Anywhere you can check the prediction later.

## Words to know
- **Candle**: one time period's open, high, low and close price
- **Failover**: automatically switching to a backup source
- **Backtesting / grading**: checking predictions against what really happened

## Honest limits (say these before someone else does)
Analysis only, not financial advice. One day's outcome is a noisy grade, so accuracy only means something over many weeks.
