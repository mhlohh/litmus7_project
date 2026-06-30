GOAL: Implement Nested Parallel-Sequential Workflow with GGUF & Thinking Aggregator

You are tasked with implementing a fully functional, production-ready agentic system in this workspace. This system must translate the conceptual architecture in aggregator_summary.md and the prototype in thinking_aggregator.py into a robust, runnable Python application.

1. Architectural Blueprint to Implement

You must build a nested Sequential-over-Parallel workflow:

Sequential Step 1 (Parallel Research): Spawn concurrent sub-agents to analyze a single input. These sub-agents must run local GGUF 1B quantized models (using llama-cpp-python or similar lightweight GGUF runtimes).

Sequential Step 2 (Thinking Aggregation): Collect all raw sub-agent outputs, filter out context logs and system prompt artifacts, resolve duplicates, and pass conflicts to a GGUF-powered reasoning "Judge". This Judge must output a <thinking> reasoning chain before outputting validated, concise JSON conforming to the Pydantic schema.

2. Technical Requirements

A. Environment & GGUF Setup

Set up a Python 3.11+ virtual environment (.venv) and install dependencies: llama-cpp-python, pydantic, pytest, and standard async libraries.

Download or configure a lightweight 1B instruction-tuned GGUF model (such as Qwen2.5-1.5B-Instruct-GGUF or Llama-3.2-1B-Instruct-GGUF) to run locally. Ensure pathing to the model is configurable via environment variables or a config file.

B. Parallel Research Agent (Step 1)

Create parallel_researcher.py utilizing Python's asyncio to load the GGUF model once and run concurrent inference queries simulating different specialized personas (e.g., Sentiment Analyst, Intent Analyst, Metadata Auditor).

Each sub-agent must return an object containing its category, raw model output (raw_text), and a calculated confidence weight.

C. Thinking Aggregator Agent (Step 2)

Translate the prototype in thinking_aggregator.py into a production-grade implementation aggregator_engine.py.

Programmatic Filter: Strip out local model log markers like [CONTEXT_LOG], [SYSTEM_PROMPT], or markdown packaging via regex.

Grouping & Deduplication: Group outputs by category and prune raw string duplicates.

Reasoning Prompt & Judge Call: Format grouped data into a structural prompt. Call the 1B GGUF model to act as a "Judge." The Judge must resolve conflicts by evaluating the priority weights and log its thought process inside <thinking>...</thinking> tags.

JSON Constraints: Enforce strict Pydantic parsing of the GGUF output using the ThinkingAggregatorReport schema.

D. System Orchestrator & CLI Entrypoint

Implement a main entrypoint main.py that orchestrates the overall flow:

Accepts user query.

Dispatches parallel sub-agents.

Feeds results to the Aggregator.

Outputs the final validated, concise JSON payload to the console or saves it to a file.

3. Implementation Steps for Antigravity Agent

Please perform the following tasks autonomously:

Analyze: Read thinking_aggregator.py and aggregator_summary.md in the workspace to grasp the core structures.

Setup Env: Initialize a virtual environment, install requirements, and draft a download script to fetch a lightweight 1B GGUF model.

Write Code: Create parallel_researcher.py, aggregator_engine.py, and main.py.

Test: Create a comprehensive test suite test_pipeline.py using pytest. Verify that context logs are filtered, conflicts are prioritized properly, duplicates are pruned, and Pydantic validation handles both valid outputs and GGUF parsing failures gracefully (fallback parsing).

Execute & Verify: Run the full sequential-parallel chain locally, capture terminal outputs, and verify that the pipeline executes successfully.

Submit all completed files and a README.md detailing how to run the system and run tests.