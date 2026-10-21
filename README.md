# LLM Market Forecaster

> 📘 New here? Start with **[READ_THIS_OVERVIEW.md](READ_THIS_OVERVIEW.md)** for a plain-English walkthrough.

A daily crypto market forecaster that runs on a local model, writes plain-English reports, and grades its own predictions the next day.

## Workflow

![Workflow diagram](docs/workflow.png)

> **Diagram key:** blue = input · purple = AI model · grey = processing · amber = storage · red = safety / guard rail · green = output

<details><summary>Diagram source (renders on GitHub)</summary>

```mermaid
flowchart TD
  C([Daily schedule · default 8 AM]):::input --> F[Fetch price candles · public APIs, no keys<br/>Kraken → Coinbase → CoinGecko if one is down]:::input
  F --> Z[Compress candles into a short market summary]:::step
  Z --> L[[Local LLM · model picked to fit the GPU]]:::ai
  L --> FC[Forecast per coin<br/>bullish / bearish / neutral + confidence]:::step
  FC --> RP([Daily written report]):::output
  FC --> DB[(SQLite forecast history)]:::store
  DB --> A[Next day: compare forecast vs. real price move]:::step
  A -->|record hit or miss| DB
  DB --> W([Web dashboard · accuracy over time]):::output

  classDef input fill:#e8f1ff,stroke:#3b82f6,color:#0b2a5b,stroke-width:1.5px
  classDef ai fill:#f1e8ff,stroke:#8b5cf6,color:#2e1065,stroke-width:1.5px
  classDef step fill:#f4f4f5,stroke:#71717a,color:#18181b,stroke-width:1.2px
  classDef store fill:#fff6e0,stroke:#d97706,color:#5a3300,stroke-width:1.2px
  classDef output fill:#e7f8ee,stroke:#16a34a,color:#073b1c,stroke-width:1.5px
  classDef guard fill:#ffecec,stroke:#dc2626,color:#5c0a0a,stroke-width:1.2px
```
</details>

## What it does
- Pulls 1h/4h/1d price candles from public exchange APIs — no account or key needed — with automatic fallback if one source is down.
- Shrinks raw price data into a short structured summary the model can reason about.
- Asks a local model for a direction call and confidence per coin, and saves a readable report.
- Checks yesterday's calls against what actually happened and tracks hit rate.
- Shows everything on a small local dashboard.

## What this project demonstrates
- Scheduled LLM pipeline with data-source failover
- Prompt design for structured, parseable model output
- Self-evaluation loop (prediction → outcome → accuracy)
- GPU-aware model selection

## Quick start
1. Install Ollama and pull a model (e.g. `qwen2.5:7b`).
2. `bash install.sh` (or `pip install -r requirements.txt`)
3. `python run.py` — dashboard at `http://localhost:5050`. Edit `config.yaml` for coins and schedule.

## Project layout
```
run.py                 ← scheduler + dashboard
config.yaml            ← coins, schedule, model
skill/market_data.py   ← fetch + compress
skill/llm_analyst.py   ← prompts + parsing
skill/accuracy.py      ← grades past forecasts
skill/database.py      ← SQLite storage
dashboard/             ← status page
```

## Notes
Analysis only. It places no trades and isn't financial advice.

## License
MIT — see [LICENSE](LICENSE).
