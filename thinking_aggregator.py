import json
import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field

# =====================================================================
# STRUCTURAL SCHEMAS FOR VALIDATED OUTPUT
# =====================================================================
class FinalInsight(BaseModel):
    category: str = Field(..., description="The unified group category.")
    resolved_data: str = Field(..., description="The highly concise data point.")
    confidence_score: float = Field(..., description="Confidence level in this resolution.")

class ThinkingAggregatorReport(BaseModel):
    thinking_process: str = Field(..., description="The step-by-step reasoning chain.")
    status: str = "success"
    findings: List[FinalInsight]

# =====================================================================
# THINKING AGGREGATOR AGENT IMPLEMENTATION
# =====================================================================
class ThinkingAggregatorAgent:
    def __init__(self, raw_parallel_data: List[Dict[str, Any]]):
        self.raw_data = raw_parallel_data

    def clean_context_bloat(self, text: str) -> str:
        """
        Filters out common local 1B GGUF model fluff like system prompt leaks,
        context log headers, or lingering markdown brackets.
        """
        text = re.sub(r'\[?(CONTEXT_LOG|SYSTEM_PROMPT|AI_LOGS|SYSTEM_LOG):?.*?\]?', '', text)
        text = text.replace("```json", "").replace("```", "")
        return text.strip()

    def build_reasoning_prompt(self, grouped_conflicts: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Generates a robust reasoning prompt that instructs the 1B GGUF judge
        to explicitly write its step-by-step resolution inside <thinking> tags.
        """
        prompt = (
            "You are the Lead Aggregator Agent. Your job is to resolve conflicts,\n"
            "remove duplicates, and extract the most accurate, concise insights.\n"
            "Below are raw, conflicting findings grouped by category from parallel agents:\n"
        )
        for category, items in grouped_conflicts.items():
            prompt += f"\nCategory: [{category}]\n"
            for i, item in enumerate(items, 1):
                prompt += f" - Finding {i}: \"{item['text']}\" (Priority Weight: {item['weight']})\n"
        prompt += (
            "\nINSTRUCTIONS:\n"
            "1. First, reason step-by-step about which findings are duplicates and which\n"
            "are the most accurate based on priority weights and logical consistency.\n"
            "2. Write your reasoning process inside a `<thinking>` block.\n"
            "3. Finally, compile the resolved, highly concise insights into the following strict JSON format:\n"
            "{\n"
            "  \"findings\": [\n"
            "    { \"category\": \"category_name\", \"resolved_data\": \"concise_resolved_insight\", \"confidence_score\": 0.95 }\n"
            "  ]\n"
            "}\n"
        )
        return prompt

    def simulate_1b_gguf_response(self, prompt: str) -> str:
        """
        Simulates the output of a local GGUF reasoning model (like Qwen2.5-1.5B-Instruct).
        """
        return """
<thinking>
- Analyzing 'user_intent': We have a conflict between 'User wants to terminate' and 'User wants to pause'. The winner is pause with weight 0.94.
- Analyzing 'system_status': Finding 1 has context bloat ('[SYSTEM_PROMPT] Connection...'), resolve to connection is stable.
</thinking>
```json
{
  "findings": [
    {
      "category": "user_intent",
      "resolved_data": "User wants to pause subscription temporarily.",
      "confidence_score": 0.94
    },
    {
      "category": "system_status",
      "resolved_data": "Connection is stable and service is online.",
      "confidence_score": 0.99
    }
  ]
}
```
"""

    def process(self) -> str:
        """
        Executes the programmatic pre-filtering, organizes the grouping,
        triggers the thinking-judgment call, parses the output, and validates the schema.
        """
        # Step 1: Pre-process and group parallel inputs
        grouped_conflicts = {}
        for entry in self.raw_data:
            category = entry.get("category", "unassigned").strip().lower()
            raw_text = entry.get("raw_text", "")
            weight = entry.get("weight", 0.0)

            clean_text = self.clean_context_bloat(raw_text)
            if not clean_text or weight < 0.2:
                continue

            if category not in grouped_conflicts:
                grouped_conflicts[category] = []
            
            # Simple deduplication check to prevent duplicate text within the same category group
            if not any(clean_text.lower() == existing['text'].lower() for existing in grouped_conflicts[category]):
                grouped_conflicts[category].append({
                    "text": clean_text,
                    "weight": weight
                })

        # Step 2: Assemble the reasoning prompt
        reasoning_prompt = self.build_reasoning_prompt(grouped_conflicts)
        
        # Step 3: Run the reasoning engine (Simulated for this script)
        raw_llm_response = self.simulate_1b_gguf_response(reasoning_prompt)

        # Step 4: Extract the Thinking and JSON segments
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', raw_llm_response, re.DOTALL)
        thinking_content = thinking_match.group(1).strip() if thinking_match else "No thinking chain recorded."

        # Robust, multi-tier JSON extraction fallback
        json_str = ""
        # Tier 1: Look for markdown JSON code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Tier 2: Look for generic markdown code blocks
            generic_code_match = re.search(r'```\s*(.*?)\s*```', raw_llm_response, re.DOTALL)
            if generic_code_match:
                json_str = generic_code_match.group(1).strip()
            else:
                # Tier 3: Find the outermost curly braces in the response
                brace_match = re.search(r'(\{.*})', raw_llm_response, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(1).strip()
                else:
                    json_str = raw_llm_response.strip()

        # Step 5: Structurally parse and validate against Pydantic models
        try:
            parsed_json = json.loads(json_str)
            
            final_report = ThinkingAggregatorReport(
                thinking_process=thinking_content,
                findings=[FinalInsight(**item) for item in parsed_json.get("findings", [])]
            )
            return final_report.model_dump_json(indent=2)
            
        except (json.JSONDecodeError, ValueError) as e:
            # Graceful error payload keeping the thinking logs intact
            return json.dumps({
                "status": "error",
                "message": f"Failed to strictly parse model's JSON response: {str(e)}",
                "extracted_raw_json_string": json_str,
                "fallback_thinking": thinking_content
            }, indent=2)

# =====================================================================
# 3. RUNTIME PIPELINE SIMULATION
# =====================================================================
if __name__ == "__main__":
    # Mock inputs generated from concurrent sub-agents in Step 1
    parallel_agent_outputs = [
        {
            "category": "user_intent",
            "raw_text": "[CONTEXT_LOG] User active. Core: User wants to terminate subscription.",
            "weight": 0.85
        },
        {
            "category": "user_intent",
            "raw_text": "User wants to pause subscription temporarily.", # Conflict
            "weight": 0.94 # High-priority conflict winner
        },
        {
            "category": "user_intent",
            "raw_text": "User wants to terminate subscription.", # Duplicate of item 1
            "weight": 0.85
        },
        {
            "category": "system_status",
            "raw_text": "[SYSTEM_PROMPT] Connection is stable and service is online.",
            "weight": 0.99
        }
    ]

    aggregator = ThinkingAggregatorAgent(parallel_agent_outputs)
    result = aggregator.process()
    print(result)