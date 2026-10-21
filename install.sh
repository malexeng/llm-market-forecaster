#!/usr/bin/env bash
# ============================================================
#  MARKET FORECASTER — ONE-CLICK INSTALLER
#  Linux Mint / Ubuntu / Any Debian-based
# ============================================================
set -e
C='\033[0;36m';G='\033[0;32m';Y='\033[1;33m';R='\033[0;31m';N='\033[0m'

echo -e "${C}"
echo "  ╔════════════════════════════════════════════╗"
echo "  ║   MARKET FORECASTER — Market Forecasting      ║"
echo "  ║   Offline LLM • No trading • No API keys  ║"
echo "  ╚════════════════════════════════════════════╝"
echo -e "${N}"

# Python
echo -e "${Y}[1/5] Checking Python...${N}"
if ! command -v python3 &>/dev/null; then
    sudo apt-get update -q && sudo apt-get install -y python3 python3-pip python3-venv
fi
PY=$(python3 -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${G}  ✓ Python $PY${N}"

# Venv
echo -e "${Y}[2/5] Creating virtual environment...${N}"
python3 -m venv venv && source venv/bin/activate
echo -e "${G}  ✓ venv ready${N}"

# Packages
echo -e "${Y}[3/5] Installing packages...${N}"
pip install --upgrade pip -q
pip install flask pyyaml requests python-dotenv -q
echo -e "${G}  ✓ Packages installed${N}"

# Ollama
echo -e "${Y}[4/5] Checking Ollama...${N}"
if command -v ollama &>/dev/null; then
    echo -e "${G}  ✓ Ollama already installed${N}"
else
    echo -e "${Y}  Installing Ollama...${N}"
    curl -fsSL https://ollama.ai/install.sh | sh
    echo -e "${G}  ✓ Ollama installed${N}"
fi

# Dirs + perms
echo -e "${Y}[5/5] Finalizing...${N}"
mkdir -p logs data reports
touch skill/__init__.py dashboard/__init__.py
chmod +x start.sh
echo -e "${G}  ✓ Done${N}"

echo ""
echo -e "${C}══════════════════════════════════════════════${N}"
echo -e "${G}  ✅ INSTALL COMPLETE${N}"
echo ""
echo -e "  ${Y}BEFORE STARTING — pull a model:${N}"
echo -e "  RTX 3090: ${C}ollama pull qwen2.5:14b${N}"
echo -e "  RTX 3060: ${C}ollama pull qwen2.5:7b${N}"
echo -e "  Any GPU:  ${C}ollama pull llama3.2:3b${N}  (smallest/fastest)"
echo ""
echo -e "  ${Y}TO START:${N}"
echo -e "  ${C}bash start.sh${N}"
echo -e "  Open ${C}http://localhost:5050${N}"
echo -e "  Click ${C}▶ START AUTO${N} or ${C}⟳ ANALYZE NOW${N}"
echo -e "${C}══════════════════════════════════════════════${N}"
