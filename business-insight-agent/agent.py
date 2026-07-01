"""
Module defining the BusinessInsightAgent class.
This class interacts with the local LM Studio instance using the OpenAI SDK
to analyze customer reviews and return structured insights in JSON format.
"""

import json
import logging
import time
from typing import List, Dict, Any, Union
from openai import OpenAI, OpenAIError
from prompt import SYSTEM_PROMPT

# Configure logging for tracking agent lifecycle and pipeline steps
logger = logging.getLogger(__name__)

class BusinessInsightAgent:
    """
    A reusable, production-ready agent designed to analyze chunks of customer
    reviews and return structured business insights. Safe for concurrent use.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        api_key: str = "lm-studio",
        model: str = "qwen2.5-3b-instruct"
    ) -> None:
        """
        Initializes the BusinessInsightAgent with the OpenAI client.

        Args:
            base_url (str): The base URL of the local LM Studio server.
            api_key (str): The API key for LM Studio (default: "lm-studio").
            model (str): The model identifier to use (default: "qwen2.5-3b-instruct").
        """
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.model = model

    def analyze_reviews(self, reviews: List[str], chunk_id: Union[int, None] = None) -> Dict[str, Any]:
        """
        Analyzes a list of customer reviews and returns structured business insights.

        This method is thread-safe and reusable, allowing multiple parallel
        orchestrator executions to run concurrently.

        Args:
            reviews (List[str]): A list of individual customer reviews.
            chunk_id (Union[int, None]): Optional ID identifier for this chunk of reviews.

        Returns:
            Dict[str, Any]: A dictionary containing structured insights inside the "analysis" key,
                            along with the "chunk_id", or an error dictionary structure.
        """
        num_reviews = len(reviews)
        logger.info(f"Received {num_reviews} reviews for business analysis (chunk_id: {chunk_id}).")

        # Initial fallback analysis dict template
        empty_analysis = {
            "strengths": [],
            "weaknesses": [],
            "customer_requests": [],
            "opportunities": [],
            "business_risks": [],
            "overall_sentiment": "",
            "summary": ""
        }

        if not reviews:
            logger.warning("Empty list of reviews provided. Skipping API request.")
            empty_analysis["summary"] = "No reviews provided for analysis."
            return {
                "chunk_id": chunk_id,
                "analysis": empty_analysis
            }

        # Join reviews into a single text block
        formatted_reviews = "\n".join(f"- {review.strip()}" for review in reviews if review.strip())

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Attempt {attempt}/{max_attempts}: Sending analysis request to LM Studio...")
            start_time = time.time()
            
            try:
                # Call local LM Studio endpoint
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Analyze these customer reviews:\n\n{formatted_reviews}"}
                    ],
                    temperature=0.2
                )
                
                # Measure response duration
                end_time = time.time()
                latency = end_time - start_time
                logger.info(f"LM Studio responded in {latency:.2f} seconds.")

                # Log token usage if available
                usage = getattr(response, "usage", None)
                if usage:
                    logger.info(
                        f"Tokens used - Prompt: {usage.prompt_tokens}, "
                        f"Completion: {usage.completion_tokens}, "
                        f"Total: {usage.total_tokens}"
                    )
                else:
                    logger.info("Token usage data not returned by model endpoint.")

                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise ValueError("LM Studio returned empty content.")

                # Try to parse response content as JSON
                parsed_json = self._parse_json(raw_content)

                # Clean, validate, and generate fallback summary if needed
                final_analysis = self._validate_and_finalize_analysis(parsed_json)

                # Return payload structured for the external aggregator
                return {
                    "chunk_id": chunk_id,
                    "analysis": final_analysis
                }

            except (OpenAIError, json.JSONDecodeError, ValueError) as e:
                end_time = time.time()
                latency = end_time - start_time
                logger.warning(
                    f"Attempt {attempt} failed after {latency:.2f} seconds. "
                    f"Error: {e.__class__.__name__}: {str(e)}"
                )

                # If this was the final attempt, return error response structure instead of crashing
                if attempt == max_attempts:
                    raw_content = ""
                    try:
                        raw_content = response.choices[0].message.content
                    except Exception:
                        pass
                    
                    return {
                        "chunk_id": chunk_id,
                        "error": f"Failed to get valid response after {max_attempts} attempts. Last error: {str(e)}",
                        "raw_response": raw_content,
                        "analysis": empty_analysis
                    }

                logger.info("Retrying review analysis query...")

            except Exception as e:
                # Catch unexpected system or runtime exceptions to prevent orchestrator crashes
                logger.exception(f"Unexpected error in review analysis pipeline: {e}")
                return {
                    "chunk_id": chunk_id,
                    "error": f"Unexpected pipeline exception: {str(e)}",
                    "raw_response": "",
                    "analysis": empty_analysis
                }

        # Fallback to satisfy type checker (normally unreachable)
        return {
            "chunk_id": chunk_id,
            "error": "Pipeline reached an unexpected terminal state.",
            "raw_response": "",
            "analysis": empty_analysis
        }

    def _parse_json(self, content: str) -> Dict[str, Any]:
        """
        Helper method to parse the raw JSON string from the model.
        Attempts to clean up markdown code block wrapping if present.
        """
        cleaned = content.strip()
        
        # Remove markdown code block wrapping (e.g. ```json ... ```)
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("LLM response did not parse as a dictionary.")
        return data

    def _validate_and_finalize_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates the output schema, ensures all keys exist, cleans whitespace,
        removes duplicate insights, and generates a fallback summary if missing.
        """
        # Ensure all standard keys exist
        cleaned: Dict[str, Any] = {
            "strengths": [],
            "weaknesses": [],
            "customer_requests": [],
            "opportunities": [],
            "business_risks": [],
            "overall_sentiment": "",
            "summary": ""
        }

        # Safe extraction for single string fields
        if "overall_sentiment" in data and data["overall_sentiment"]:
            cleaned["overall_sentiment"] = str(data["overall_sentiment"]).strip()
        
        # Keys containing lists that need deduplication
        list_keys = ["strengths", "weaknesses", "customer_requests", "opportunities", "business_risks"]
        
        for key in list_keys:
            if key in data and isinstance(data[key], list):
                seen_items = set()
                unique_list = []
                for item in data[key]:
                    if item is not None:
                        val = str(item).strip()
                        # Deduplicate case-insensitively while preserving original string casing
                        if val and val.lower() not in seen_items:
                            seen_items.add(val.lower())
                            unique_list.append(val)
                cleaned[key] = unique_list

        # Verify or generate summary
        has_summary = False
        if "summary" in data and data["summary"]:
            summary_str = str(data["summary"]).strip()
            if summary_str:
                cleaned["summary"] = summary_str
                has_summary = True

        if not has_summary:
            logger.info("Model did not provide a summary. Generating fallback summary from insights.")
            cleaned["summary"] = self._generate_fallback_summary(cleaned)

        return cleaned

    def _generate_fallback_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Generates a 2-3 sentence business summary based on the extracted insights
        if the model failed to provide one.
        """
        strengths = analysis.get("strengths", [])
        weaknesses = analysis.get("weaknesses", [])
        requests = analysis.get("customer_requests", [])
        
        sentences = []
        
        # 1. Summary of strengths
        if strengths:
            top_strengths = ", ".join(strengths[:3])
            sentences.append(f"Key product strengths highlighted by customers include {top_strengths}.")
        else:
            sentences.append("The analyzed customer reviews did not highlight major product strengths.")
            
        # 2. Summary of weaknesses
        if weaknesses:
            top_weaknesses = ", ".join(weaknesses[:3])
            sentences.append(f"However, critical weaknesses were noted regarding {top_weaknesses}.")
        else:
            sentences.append("No significant weaknesses or operational issues were identified.")
            
        # 3. Summary of customer requests or overall outlook
        if requests:
            top_requests = ", ".join(requests[:2])
            sentences.append(f"To address customer needs, priorities should focus on implementing {top_requests}.")
        else:
            sentences.append("Overall customer sentiment is generally stable with standard expectations.")
            
        return " ".join(sentences)


# =====================================================================
# Google Agent Development Kit (ADK) Integration
# =====================================================================
_adk_model_registered = False

def register_adk_model() -> None:
    """
    Registers the BusinessInsightLlm model under the name 'business-insight-model'
    in the google-adk LLMRegistry if it has not been registered yet.

    Raises:
        ImportError: If the 'google-adk' package is missing when explicitly called.
    """
    global _adk_model_registered
    if _adk_model_registered:
        return

    try:
        from typing import AsyncGenerator
        from google.adk.models import BaseLlm, LLMRegistry, LlmRequest, LlmResponse
        from google.genai.types import Content, Part

        class BusinessInsightLlm(BaseLlm):
            """
            A custom ADK LLM Model wrapper that plugs our BusinessInsightAgent
            directly into the Google Agent Development Kit (ADK) ecosystem.
            """

            @classmethod
            def supported_models(cls) -> List[str]:
                """
                Registers the unique model identifier in the ADK registry.
                """
                return [r"^business-insight-model$"]

            async def generate_content_async(
                self, llm_request: LlmRequest, stream: bool = False
            ) -> AsyncGenerator[LlmResponse, None]:
                """
                Executes review analysis via the local agent and returns a standard
                ADK LlmResponse.
                """
                # 1. Extract reviews/prompts from the contents
                texts = []
                for content in llm_request.contents:
                    for part in content.parts:
                        if part.text:
                            texts.append(part.text)

                # 2. Split text lines into lists of individual reviews
                reviews = []
                for text in texts:
                    # Remove bullets/dashes/numbered prefixes for cleaner analysis
                    lines = [
                        line.strip().lstrip("-*• ").strip()
                        for line in text.splitlines()
                        if line.strip()
                    ]
                    reviews.extend(lines)

                # 3. Call the core review analysis logic (automatically handles retries & parsing)
                agent = BusinessInsightAgent()
                result = agent.analyze_reviews(reviews)

                # 4. Yield the serialized output as the LlmResponse
                response_text = json.dumps(result, indent=2)
                yield LlmResponse(
                    content=Content(
                        role="model",
                        parts=[Part(text=response_text)]
                    )
                )

        # Register the model to the ADK LLMRegistry
        LLMRegistry.register(BusinessInsightLlm)
        _adk_model_registered = True
        logger.info("Successfully registered BusinessInsightLlm in google-adk LLMRegistry.")
    except ImportError as e:
        raise ImportError(
            "The 'google-adk' package is required to use this feature. "
            "Please install it using: pip install google-adk"
        ) from e


def get_adk_agent(name: str = "business_insight_agent") -> Any:
    """
    Creates and returns a google-adk Agent instance preconfigured with the
    'business-insight-model'.

    Args:
        name (str): The name of the ADK agent (default: "business_insight_agent").

    Returns:
        Agent: A google-adk Agent instance.
    """
    # Trigger model registration first
    register_adk_model()
    
    from google.adk.agents import Agent
    return Agent(
        model="business-insight-model",
        name=name,
        description="Extracts structured business insights from customer reviews."
    )


# Perform automatic registration on import if google-adk is available in the environment
try:
    register_adk_model()
except ImportError:
    # Silent skip if google-adk is not installed
    pass


