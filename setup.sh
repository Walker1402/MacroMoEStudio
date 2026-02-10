#!/bin/bash
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Pulling Ollama Models (This may take a while)..."
ollama pull gemma3:4b
ollama pull qwen3-vl:4b
ollama pull phi4-mini-reasoning:3.8b-q4_K_M

echo "Setup Complete!"
echo "Run the app with: python3 MacroMoEStudio.py"
