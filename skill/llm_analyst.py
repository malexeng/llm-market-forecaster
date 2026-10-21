"""
skill/llm_analyst.py
Interfaces with local Ollama LLM.
Auto-detects GPU and picks best model.
Builds structured prompts, parses JSON forecasts.
"""

import json
import logging
import re
import subprocess
from typing import Dict, Optional
import requests

logger = logging.getLogger("llm_analyst")

OLLAMA_HOST = "http://localhost:11434"

ANALYST_SYSTEM = """You are an expert cryptocurrency market analyst.
You study technical indicators and market structure to generate daily forecasts.
You are rigorous, data-driven, and honest about uncertainty.
You NEVER give financial advice. You analyze patterns and probabilities.

Your forecasts will be checked against reality to measure your accuracy over time.
This makes you accountable — be precise, not vague.

ALWAYS respond with valid JSON only. No markdown. No extra text.
"""

FORECAST_PROMPT = """Analyze this market data and generate your daily forecast.

{context_text}

Respond with this exact JSON structure:
{{
  "direction": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 55-95,
  "reasoning": "2-3 sentences explaining WHY based on the indicators above",
  "key_levels": {{
    "support": <number>,
    "resistance": <number>,
    "invalidation": <price that would prove forecast wrong>
  }},
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "what_to_watch": "one specific thing to monitor in next 24h",
  "summary": "plain English paragraph (3-5 sentences) a non-trader could understand"
}}"""

REPORT_PROMPT = """You have analyzed these {n} markets today:

{forecasts_text}

Write a cohesive daily market report covering:
1. Overall market sentiment
2. Key themes across all assets
3. What the data suggests for the next 24 hours
4. Biggest risks and opportunities
5. One thing you learned from today's data

Write in plain English. Be specific. Avoid clichés like "the market could go up or down."
Target length: 300-400 words. This is not financial advice — it is technical analysis education.
"""


# ── GPU Auto-detect ───────────────────────────────────────────
def detect_gpu_and_model(config_model: str = "") -> str:
    """Auto-detect GPU VRAM and pick best Ollama model."""
    if config_model:
        return config_model

    vram_gb = 0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            vrams = [int(v.strip()) for v in result.stdout.strip().split("\n") if v.strip()]
            vram_gb = max(vrams) / 1024
            logger.info(f"NVIDIA GPU detected: {vram_gb:.1f}GB VRAM")
    except Exception:
        pass

    if vram_gb == 0:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                matches = re.findall(r'(\d+)', result.stdout)
                if matches:
                    vram_gb = int(matches[0]) / 1024
                    logger.info(f"AMD GPU detected: {vram_gb:.1f}GB VRAM")
        except Exception:
            pass

    # Pick model based on VRAM
    if vram_gb >= 20:
        preferred = ["qwen2.5:14b", "qwen2.5:7b", "mistral:7b", "llama3.2:3b"]
        logger.info("RTX 3090 class detected → trying qwen2.5:14b")
    elif vram_gb >= 10:
        preferred = ["qwen2.5:7b", "qwen2.5:14b", "mistral:7b", "llama3.2:3b"]
        logger.info("RTX 3060 class detected → trying qwen2.5:7b")
    else:
        preferred = ["llama3.2:3b", "qwen2.5:7b", "mistral:7b"]
        logger.info("Low/no GPU detected → trying smallest model")

    # Check what's actually installed in Ollama
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        installed = [m["name"] for m in r.json().get("models", [])]
        logger.info(f"Installed models: {installed}")
        for model in preferred:
            for inst in installed:
                if model.split(":")[0] in inst:
                    logger.info(f"Selected model: {inst}")
                    return inst
        # Fallback: use whatever is installed
        if installed:
            logger.info(f"Fallback model: {installed[0]}")
            return installed[0]
    except Exception as e:
        logger.warning(f"Could not query Ollama models: {e}")

    return "qwen2.5:7b"   # Final default


# ── LLM Interface ─────────────────────────────────────────────
class LLMAnalyst:

    def __init__(self, config: dict):
        self.host    = config.get("ollama_host", OLLAMA_HOST)
        self.model   = detect_gpu_and_model(config.get("ollama_model", ""))
        self.timeout = 60

    def is_online(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _call(self, system: str, user: str) -> Optional[str]:
        try:
            r = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 600}
                },
                timeout=self.timeout
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
        except requests.Timeout:
            logger.error(f"LLM timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _context_to_text(self, ctx: Dict) -> str:
        """Converts compressed market context dict → readable text for LLM."""
        return f"""
SYMBOL: {ctx['symbol']}
Current Price: ${ctx['price']:,}
Trend ({20}-candle): {ctx['trend']}
Volatility: {ctx['volatility']}

PRICE CHANGES:
  1h:  {ctx['chg_1h']:+.2f}%
  24h: {ctx['chg_1d']:+.2f}%
  7d:  {ctx['chg_7d']:+.2f}%

TECHNICAL INDICATORS:
  RSI(14):  {ctx['rsi']} — {ctx['rsi_label']}
  MACD:     {ctx['macd']} / Signal: {ctx['macd_signal']} — {ctx['macd_label']}
  BB Upper: ${ctx['bb_upper']}  Mid: ${ctx['bb_mid']}  Lower: ${ctx['bb_lower']}
  BB Position: {ctx['bb_position']}

STRUCTURE:
  Support:    ${ctx['support']}
  Resistance: ${ctx['resistance']}
  Pattern:    {ctx['pattern']}
  Volume:     {ctx['volume_ratio']}x average — {ctx['volume_label']}

Based on {ctx['candle_count']} hourly candles.
""".strip()

    def forecast(self, context: Dict) -> Optional[Dict]:
        """Generate a structured forecast for one symbol."""
        context_text = self._context_to_text(context)
        prompt = FORECAST_PROMPT.format(context_text=context_text)

        logger.info(f"  Asking {self.model} to forecast {context['symbol']}...")
        raw = self._call(ANALYST_SYSTEM, prompt)
        if not raw:
            return None

        # Parse JSON
        try:
            clean = re.sub(r'```(?:json)?', '', raw).strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not match:
                raise ValueError("No JSON found")
            data = json.loads(match.group())
            data["symbol"]     = context["symbol"]
            data["price"]      = context["price"]
            data["model_used"] = self.model
            data["raw"]        = raw
            return data
        except Exception as e:
            logger.error(f"  Parse error: {e} | Raw: {raw[:300]}")
            return None

    def generate_daily_report(self, forecasts: list) -> str:
        """Synthesize all symbol forecasts into one cohesive daily report."""
        if not forecasts:
            return "No forecasts available for report generation."

        forecasts_text = "\n\n".join([
            f"=== {f['symbol']} ===\n"
            f"Direction: {f.get('direction')} ({f.get('confidence')}% confidence)\n"
            f"Reasoning: {f.get('reasoning','')}\n"
            f"Key Levels: Support ${f.get('key_levels',{}).get('support','?')} | "
            f"Resistance ${f.get('key_levels',{}).get('resistance','?')}\n"
            f"Risk: {f.get('risk_level','?')} | Watch: {f.get('what_to_watch','?')}"
            for f in forecasts
        ])

        prompt = REPORT_PROMPT.format(
            n=len(forecasts),
            forecasts_text=forecasts_text
        )

        logger.info(f"  Generating daily report from {len(forecasts)} forecasts...")
        raw = self._call(ANALYST_SYSTEM, prompt)
        return raw or "Report generation failed — LLM unavailable."
