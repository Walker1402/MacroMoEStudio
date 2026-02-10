Macro-MoE Studio: The Local SLM Orchestrator
Macro-MoE Studio is a native, high-performance desktop orchestrator designed to unify specialized Small Language Models (SLMs) into a cohesive "Mixture of Experts" (MoE) workflow. It provides a low-latency, privacy-first alternative to cloud-based agents by managing local hardware resources with precision.
🏗️ Technical Breakdown

The core philosophy of this project is Orchestration over Integration. Instead of relying on a single, massive model, it uses a lightweight router to engage "expert" models only when needed.
1. The Expert Routing Logic

The backend utilizes a priority-based routing algorithm to select the optimal model for every request:

    Force Logic (Highest Priority): Bypasses all triggers to engage phi4-mini-reasoning for deep debugging or complex logic.

    Vision Trigger: Detects image attachments (.png, .jpg, .jpeg) and automatically loads qwen3-vl.

    Keyword Analysis: Scans prompts for "code", "math", or "cmd" to switch to the reasoning expert.

    Fallback: Uses gemma3 as the default generalist for standard natural language processing.

2. Dynamic VRAM Lifecycle

To solve the "VRAM Deadlock" common in local AI, the orchestrator manages the model lifecycle via the Ollama API:

    Keep-Alive Signals: Uses a 5-minute keep_alive window to maintain responsiveness while ensuring the GPU is eventually flushed for other system tasks.

    Ephemeral Context: Attached files are processed as transient snapshots and immediately purged from memory after response generation to prevent context window bloat.

3. Agentic Execution Loop

Unlike standard chatbots, this studio has "hands" through a secure command-execution bridge:

    Regex Extraction: The backend identifies system commands wrapped in <cmd> tags.

    Approval Gate: A native UI popup halts execution until you explicitly authorize the command, preventing unauthorized system changes.

    Subprocess Integration: Authorized commands run via Python’s subprocess module, with output piped directly back into the chat context.

🎯 Use Cases
🛠️ Use Case 1: The Dev-Ops "Second Pair of Eyes"

    Trigger: Upload a screenshot of a terminal error or server log.

    Workflow: The Vision Expert OCRs the error → The Logic Expert analyzes the stack trace → The AI suggests a fix via a <cmd> tag.

    Result: You click "Yes," and the error is resolved natively on your system.

🧠 Use Case 2: Privacy-First Personal Knowledge Base

    Trigger: Use the /remember slash command to store sensitive project details.

    Workflow: Facts are stored in memory.json locally and injected into every prompt's system context.

    Result: A fully air-gapped assistant that knows your specific workflows without your data ever leaving your machine.

📉 Use Case 3: Performance-First Productivity on Budget Hardware

    Trigger: Running multiple specialized 4B models on a laptop with limited VRAM.

    Workflow: The orchestrator unloads the vision model once OCR is complete to give 100% of the GPU to the reasoning model.

    Result: High-end AI agent performance on mid-range hardware.

📂 Repository Structure

    LocalAI.py: The core application logic and Tkinter/CustomTkinter GUI.

    requirements.txt: Minimal dependencies (primarily customtkinter).

    setup.bat: A one-click bootstrap script for Windows that installs dependencies and auto-pulls all required Ollama models.

    .gitignore: Pre-configured to prevent your private chats/ and memory.json from ever being uploaded to GitHub.
