# Macro-MoE Studio: The Local SLM Orchestrator

Macro-MoE Studio is a native, high-performance desktop orchestrator designed to unify specialized Small Language Models (SLMs) into a cohesive "Mixture of Experts" (MoE) workflow. It provides a low-latency, privacy-first alternative to cloud-based agents by managing local hardware resources with precision.

##  Technical Breakdown

The core philosophy of this project is **Orchestration over Integration**. Instead of relying on a single, massive model, it uses a lightweight router to engage "expert" models only when needed.

### 1. The Expert Routing Logic
The backend utilizes a priority-based routing algorithm to select the optimal model for every request:
* **Force Logic (Highest Priority):** Bypasses all triggers to engage `phi4-mini-reasoning` for deep debugging or complex logic.
* **Vision Trigger:** Detects image attachments (`.png`, `.jpg`, `.jpeg`) and automatically loads `qwen3-vl`.
* **Keyword Analysis:** Scans prompts for "code", "math", or "cmd" to switch to the reasoning expert.
* **Fallback:** Uses `gemma3` as the default generalist for standard natural language processing.

### 2. Dynamic VRAM Lifecycle
To solve the "VRAM Deadlock" common in local AI, the orchestrator manages the model lifecycle via the Ollama API:
* **Keep-Alive Signals:** Uses a 5-minute `keep_alive` window to maintain responsiveness while ensuring the GPU is eventually flushed.
* **Ephemeral Context:** Attached files are processed as transient snapshots and immediately purged from memory after response generation.

### 3. Agentic Execution Loop
Unlike standard chatbots, this studio has "hands" through a secure command-execution bridge:
* **Regex Extraction:** The backend identifies system commands wrapped in `<cmd>` tags.
* **Approval Gate:** A native UI popup halts execution until you explicitly authorize the command.
* **Secure Execution:** Authorized commands run via Python’s subprocess module with strict whitelist filtering.

---

## Installation

### Prerequisites
1.  **Install Python 3.10+**
2.  **Install Ollama:** [Download here](https://ollama.com) and ensure it is running (`ollama serve`).

###  Quick Start (Windows)
1.  Double-click `setup.bat`.
    * *This will install dependencies and pull the required models (gemma3, qwen3-vl, phi4-mini-reasoning).*
2.  The app will launch automatically.

### Quick Start (Linux / macOS)
1.  Open a terminal in the folder.
2.  Run:
    ```bash
    chmod +x setup.sh
    ./setup.sh
    ```

---

## Repository Structure

* `MacroMoEStudio.py`: The core application logic and GUI.
* `requirements.txt`: Minimal dependencies.
* `setup.bat`: One-click bootstrap for Windows.
* `setup.sh`: Bootstrap script for Linux/macOS.
* `.gitignore`: Prevents `chats/` and `memory.json` from being uploaded.

## License
MIT License. See `LICENSE` for details.
