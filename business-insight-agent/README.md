# Business Insight Agent

A reusable, production-ready AI sub-agent designed to extract structured business insights from customer reviews using local LLMs (via LM Studio).

This agent is built as a self-contained, thread-safe component to be easily instantiated and called concurrently by an orchestrator or aggregator in a multi-agent system.

---

## Project Structure

- **[app.py](file:///c:/codespace/litmus7_project/business-insight-agent/app.py)**: Driver script that loads sample reviews, instantiates the agent, executes analysis, and pretty-prints the JSON results.
- **[agent.py](file:///c:/codespace/litmus7_project/business-insight-agent/agent.py)**: Contains the `BusinessInsightAgent` class, which manages the local LM Studio API client, executes inference, handles exceptions gracefully, and processes JSON parsing.
- **[prompt.py](file:///c:/codespace/litmus7_project/business-insight-agent/prompt.py)**: Defines the system prompt guiding the local LLM to return structured business analysis strictly matching the requested JSON format.
- **[requirements.txt](file:///c:/codespace/litmus7_project/business-insight-agent/requirements.txt)**: Python package dependencies.
- **[sample_reviews.txt](file:///c:/codespace/litmus7_project/business-insight-agent/sample_reviews.txt)**: A list of customer reviews (one per line) used for demonstrating the agent's capabilities.

---

## Setup Instructions

### 1. Install Dependencies

Ensure you have Python 3.8 or higher installed. Start by setting up a virtual environment and installing the required packages:

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (CMD):
.venv\Scripts\activate.bat
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure LM Studio

1. **Download & Install LM Studio**: Ensure you have [LM Studio](https://lmstudio.ai/) installed on your local machine.
2. **Search and Download the Model**:
   - Open LM Studio and go to the **Search** tab (magnifying glass icon).
   - Search for `Qwen2.5-3B-Instruct`.
   - Download one of the recommended GGUF versions (e.g., `qwen2.5-3b-instruct-gguf` or similar `Q4_K_M` / `Q5_K_M` quantization).
3. **Load the Model**:
   - Go to the **Local Server** tab (the server/plug icon on the left sidebar).
   - From the dropdown menu at the top, select the downloaded `Qwen2.5-3B-Instruct` model to load it.
4. **Start the Local Server**:
   - Set the port to `1234` (default).
   - Set the bind address to `127.0.0.1` (localhost).
   - Click the **Start Server** button. The server will expose an OpenAI-compatible endpoint at `http://127.0.0.1:1234/v1`.

### 3. Run the Application

With LM Studio's server running and the Qwen model loaded, run the application:

```bash
python app.py
```

---

## JSON Output Schema

The agent returns a parsed Python dictionary (or a raw JSON string if parsing fails) conforming to the following structure:

```json
{
  "strengths": [
    "Key positive aspects mentioned by customers."
  ],
  "weaknesses": [
    "Key negative aspects or issues mentioned by customers."
  ],
  "customer_requests": [
    "Explicit feature requests, suggestions, or improvements."
  ],
  "opportunities": [
    "Potential growth areas or features based on customer feedback."
  ],
  "business_risks": [
    "Critical threats, severe defects, churn risks, or safety concerns."
  ],
  "overall_sentiment": "Overall sentiment string (e.g., Positive, Mixed, Negative)",
  "summary": "Concise high-level summary of findings."
}
```

---

## Integration and Reusability

To integrate this agent into your larger multi-agent system or run it concurrently inside parallel aggregators:

```python
from agent import BusinessInsightAgent

# Initialize the agent
agent = BusinessInsightAgent(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio",
    model="qwen2.5-3b-instruct"
)

# Analyze a batch of reviews
reviews = ["Review 1 text", "Review 2 text", "Review 3 text"]
result = agent.analyze_reviews(reviews)

if isinstance(result, dict):
    print("Success:", result["overall_sentiment"])
else:
    print("Failed to parse JSON. Raw output:", result)
```

### Design Considerations for Parallel Orchestration:
- **Thread-Safety**: The `analyze_reviews` method maintains no request-specific state on the `BusinessInsightAgent` instance. All inference is completely stateless, making it safe to run parallel calls on the same agent instance.
- **Robust Response Parsing**: The helper parses JSON strictly, stripping markdown wrapping if it is returned by the LLM.
- **API Resilience**: Any HTTP or network connection exceptions during inference are caught and returned as structured error messages instead of raising exceptions that would crash the pipeline.

---

## Google Agent Development Kit (ADK) Integration

The project provides a built-in wrapper that registers `BusinessInsightAgent` as a custom LLM model named **`business-insight-model`** in the `google-adk` registry. This allows any parent `Agent` (such as `root_agent`) or `ParallelAgent` to use the agent as an underlying model.

### Registering and Using the Model in ADK

Importing `agent` automatically registers `BusinessInsightLlm` under the model identifier `business-insight-model` in the `LLMRegistry`.

```python
import asyncio
from google.adk.agents import Agent
from google.genai import types

# 1. Importing registers the model
import agent

# 2. Define an Agent referencing the registered model
root_agent = Agent(
    model="business-insight-model",
    name="my_analyst"
)

# 3. Running the agent
# Pass text content containing reviews (delimited by newlines)
```

A complete integration script demonstrating single-agent execution and concurrent execution via `ParallelAgent` is available in **[adk_integration_example.py](file:///c:/codespace/litmus7_project/business-insight-agent/adk_integration_example.py)**.

