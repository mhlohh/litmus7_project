import json
import re
import os
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from lm_studio_llm import LMStudioLlm

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
        # Initialize our custom LM Studio LLM for the Judge Agent
        self.lm_studio_model = LMStudioLlm(model=os.getenv("LM_STUDIO_MODEL_NAME", "Qwen2.5-Coder-7B-Instruct-GGUF"))

    def clean_context_bloat(self, text: str) -> str:
        """
        Filters out common local GGUF model fluff like system prompt leaks,
        context log headers, lingering markdown brackets, or confidence indicators.
        """
        # Strip system / context logs
        text = re.sub(r'\[?(CONTEXT_LOG|SYSTEM_PROMPT|AI_LOGS|SYSTEM_LOG):?.*?\]?', '', text, flags=re.IGNORECASE)
        # Strip confidence indicators
        text = re.sub(r'Confidence:\s*[0-9.]+', '', text, flags=re.IGNORECASE)
        # Strip markdown tags
        text = text.replace("```json", "").replace("```", "")
        return text.strip()

    def build_reasoning_prompt(self, grouped_conflicts: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Generates a robust reasoning prompt that instructs the judge agent
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

    def fallback_parse_json(self, raw_llm_response: str) -> Dict[str, Any]:
        """
        Regex-based fallback extraction if the model fails to return standard JSON.
        """
        findings = []
        # Find matches resembling {"category": "...", "resolved_data": "...", "confidence_score": 0.95}
        matches = re.finditer(
            r'\{\s*"category"\s*:\s*"([^"]+)"\s*,\s*"resolved_data"\s*:\s*"([^"]+)"\s*,\s*"confidence_score"\s*:\s*([0-9.]+)\s*\}',
            raw_llm_response
        )
        for m in matches:
            try:
                findings.append({
                    "category": m.group(1),
                    "resolved_data": m.group(2),
                    "confidence_score": float(m.group(3))
                })
            except Exception:
                pass
        
        # If we failed to parse using the formal findings schema, look for loose pairs
        if not findings:
            loose_matches = re.finditer(
                r'"category"\s*:\s*"([^"]+)"\s*,\s*"resolved_data"\s*:\s*"([^"]+)"',
                raw_llm_response
            )
            for lm in loose_matches:
                findings.append({
                    "category": lm.group(1),
                    "resolved_data": lm.group(2),
                    "confidence_score": 0.85
                })

        return {"findings": findings}

    async def process(self) -> str:
        """
        Executes the programmatic pre-filtering, organizes the grouping,
        triggers the thinking-judgment call to LM Studio, parses the output, and validates the schema.
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
            
            # Simple deduplication check within the same category group
            if not any(clean_text.lower() == existing['text'].lower() for existing in grouped_conflicts[category]):
                grouped_conflicts[category].append({
                    "text": clean_text,
                    "weight": weight
                })

        # Step 2: Assemble the reasoning prompt
        reasoning_prompt = self.build_reasoning_prompt(grouped_conflicts)
        
        # Step 3: Call Judge Agent using Google ADK & LM Studio LLM
        judge_agent = Agent(
            model=self.lm_studio_model,
            name="aggregator_judge",
            description="Resolves conflicts and generates unified findings.",
            instruction="You are the Lead Aggregator Agent. Output a <thinking> process, then output the strict JSON findings."
        )

        runner = InMemoryRunner(agent=judge_agent)
        session = await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id="user",
        )
        
        raw_llm_response = ""
        try:
            async for event in runner.run_async(
                user_id="user",
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=reasoning_prompt)]
                )
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                raw_llm_response += part.text
        except Exception as e:
            raw_llm_response = f"<thinking>Failed to query Judge Agent: {str(e)}</thinking>"

        # Step 4: Extract the Thinking and JSON segments
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', raw_llm_response, re.DOTALL)
        thinking_content = thinking_match.group(1).strip() if thinking_match else "No thinking chain recorded."

        # Robust, multi-tier JSON extraction
        json_str = ""
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            generic_code_match = re.search(r'```\s*(.*?)\s*```', raw_llm_response, re.DOTALL)
            if generic_code_match:
                json_str = generic_code_match.group(1).strip()
            else:
                brace_match = re.search(r'(\{.*})', raw_llm_response, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(1).strip()
                else:
                    json_str = raw_llm_response.strip()

        # Step 5: Structurally parse and validate against Pydantic models
        parsed_json = None
        try:
            # Normalize common issues like single quotes
            normalized_json_str = json_str.replace("'", '"')
            parsed_json = json.loads(normalized_json_str)
        except (json.JSONDecodeError, ValueError):
            # Fall back to regex extraction
            parsed_json = self.fallback_parse_json(raw_llm_response)

        # Enforce schemas
        try:
            findings_list = []
            for item in parsed_json.get("findings", []):
                findings_list.append(FinalInsight(
                    category=item.get("category", "unassigned"),
                    resolved_data=item.get("resolved_data", ""),
                    confidence_score=float(item.get("confidence_score", 0.8))
                ))
            
            final_report = ThinkingAggregatorReport(
                thinking_process=thinking_content,
                findings=findings_list
            )
            return final_report.model_dump_json(indent=2)
            
        except Exception as e:
            # Graceful error payload keeping the thinking logs intact
            return json.dumps({
                "status": "error",
                "message": f"Failed to strictly parse/validate model's response: {str(e)}",
                "extracted_raw_json_string": json_str,
                "fallback_thinking": thinking_content,
                "parsed_fallback_findings": parsed_json.get("findings", []) if parsed_json else []
            }, indent=2)
