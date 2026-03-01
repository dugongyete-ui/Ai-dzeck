from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI, RateLimitError
from app.domain.external.llm import LLM
from app.core.config import get_settings
import logging
import asyncio
import re


logger = logging.getLogger(__name__)

class OpenAILLM(LLM):
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base
        )
        
        self._model_name = settings.model_name
        self._temperature = settings.temperature
        self._max_tokens = settings.max_tokens
        logger.info(f"Initialized OpenAI LLM with model: {self._model_name}")
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    @property
    def temperature(self) -> float:
        return self._temperature
    
    @property
    def max_tokens(self) -> int:
        return self._max_tokens
    
    async def ask(self, messages: List[Dict[str, str]],
                tools: Optional[List[Dict[str, Any]]] = None,
                response_format: Optional[Dict[str, Any]] = None,
                tool_choice: Optional[str] = None) -> Dict[str, Any]:
        """Send chat request to OpenAI API with retry mechanism"""
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.info(f"Retrying LLM request (attempt {attempt + 1}/{max_retries + 1}) after {delay:.0f}s delay")
                    await asyncio.sleep(delay)

                kwargs = {
                    "model": self._model_name,
                    "temperature": self._temperature,
                    "max_tokens": self._max_tokens,
                    "messages": messages,
                }

                if tools:
                    # When tools are provided, do NOT send response_format.
                    # Mixing tools + response_format=json_object confuses free/proxy APIs
                    # (like pollinations.ai) and causes malformed tool call names.
                    # The system prompt already instructs the model to output JSON when done.
                    logger.debug(f"Sending request with {len(tools)} tools, model: {self._model_name}, attempt: {attempt + 1}")
                    kwargs["tools"] = tools
                    if tool_choice:
                        kwargs["tool_choice"] = tool_choice
                else:
                    # No tools — safe to apply response_format (for planner JSON responses)
                    logger.debug(f"Sending request without tools, model: {self._model_name}, attempt: {attempt + 1}")
                    if response_format:
                        kwargs["response_format"] = response_format

                response = await self.client.chat.completions.create(**kwargs)

                logger.debug(f"LLM response received: model={self._model_name}")

                if not response or not response.choices:
                    error_msg = f"LLM returned empty response (no choices) on attempt {attempt + 1}"
                    logger.error(error_msg)
                    if attempt == max_retries:
                        raise ValueError(f"Failed after {max_retries + 1} attempts: {error_msg}")
                    continue

                result = response.choices[0].message.model_dump()

                # Sanitize tool call function names — free API proxies sometimes
                # produce garbage like "file_write?commentary=...<|end|><|start|>assistant"
                if result.get("tool_calls"):
                    cleaned_tool_calls = []
                    for tc in result["tool_calls"]:
                        if tc.get("function") and tc["function"].get("name"):
                            raw_name = tc["function"]["name"]
                            # Extract only the clean function name (alphanumeric + underscore)
                            clean_name = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', raw_name)
                            if clean_name:
                                if raw_name != clean_name.group(1):
                                    logger.warning(f"Sanitized malformed tool name: {raw_name!r} → {clean_name.group(1)!r}")
                                tc["function"]["name"] = clean_name.group(1)
                                cleaned_tool_calls.append(tc)
                            else:
                                logger.warning(f"Skipping tool call with unparseable name: {raw_name!r}")
                        else:
                            cleaned_tool_calls.append(tc)
                    result["tool_calls"] = cleaned_tool_calls if cleaned_tool_calls else None

                return result

            except RateLimitError as e:
                # Free API rate limit — wait longer before retry
                rate_limit_delay = 30.0 * (attempt + 1)
                logger.warning(f"Rate limit hit (attempt {attempt + 1}), waiting {rate_limit_delay:.0f}s before retry...")
                if attempt == max_retries:
                    raise e
                await asyncio.sleep(rate_limit_delay)
                continue

            except Exception as e:
                error_msg = f"Error calling LLM API on attempt {attempt + 1}: {str(e)}"
                logger.error(error_msg)
                if attempt == max_retries:
                    raise e
                continue
