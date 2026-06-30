import os
import httpx
from typing import AsyncGenerator, Optional
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

class LMStudioLlm(BaseLlm):
    """
    Google ADK LLM adapter for LM Studio.
    Bridges ADK agents to an OpenAI-compatible endpoint like http://127.0.0.1:1234/v1
    """
    base_url: str = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")

    @classmethod
    def supported_models(cls) -> list[str]:
        # Support any model name matched via regex or configuration
        return [".*"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        # 1. Translate system instruction if provided in the ADK config
        messages = []
        if llm_request.config and llm_request.config.system_instruction:
            sys_inst = llm_request.config.system_instruction
            if hasattr(sys_inst, "parts"):
                sys_text = "".join(part.text for part in sys_inst.parts if part.text)
            elif isinstance(sys_inst, str):
                sys_text = sys_inst
            else:
                sys_text = str(sys_inst)
            
            if sys_text.strip():
                messages.append({"role": "system", "content": sys_text.strip()})

        # 2. Map contents to messages
        for content in llm_request.contents:
            role = content.role
            # ADK uses 'model' or 'assistant' depending on flow, map to OpenAI standard
            if role == "model":
                role = "assistant"
            elif role not in ["user", "system", "assistant"]:
                role = "user"

            parts_text = []
            if content.parts:
                for part in content.parts:
                    if part.text:
                        parts_text.append(part.text)
            
            content_str = "".join(parts_text).strip()
            # Avoid sending empty messages
            if content_str:
                messages.append({"role": role, "content": content_str})

        # Ensure we have at least one message
        if not messages:
            messages.append({"role": "user", "content": "Hello"})

        model_name = self.model or os.getenv("LM_STUDIO_MODEL_NAME", "Qwen2.5-Coder-7B-Instruct-GGUF")

        # 3. Call LM Studio's chat completion endpoint
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": llm_request.config.temperature if (llm_request.config and llm_request.config.temperature is not None) else 0.7,
            }
            
            # Enforce JSON formatting if response schema or constraint is requested
            if llm_request.config and llm_request.config.response_mime_type == "application/json":
                payload["response_format"] = {"type": "json_object"}

            url = f"{self.base_url.rstrip('/')}/chat/completions"
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            res_json = response.json()
            reply_text = res_json["choices"][0]["message"]["content"]

            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=reply_text)]
                ),
                partial=False
            )
