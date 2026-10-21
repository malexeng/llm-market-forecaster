#!/usr/bin/env bash
[ -d "venv" ] && source venv/bin/activate

# Start Ollama in background if not running
if ! pgrep -x ollama > /dev/null; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
fi

echo ""
echo "  MARKET FORECASTER starting..."
echo "  Dashboard → http://localhost:5050"
echo "  Stop      → Ctrl+C"
echo ""
python3 run.py
