from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Final, Protocol, Self, cast, overload

import litellm
from loguru import logger
from openai.lib._parsing import parse_chat_completion
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from openai.types.chat.parsed_chat_completion import ParsedChatCompletionMessage
from pydantic import BaseModel, ValidationError

from toolmaker.llm.completions import completion_factory
from toolmaker.utils.logging import tlog

MAX_COST: Final[float] = 5.0  # dollars
MAX_LLM_RETRIES: Final[int] = int(os.getenv("LLM_MAX_RETRIES", "15"))
LLM_MODEL: Final[str] = os.getenv("LLM_MODEL", "gemini/gemini-pro")
LLM_MODEL_REASONING: Final[str] = os.getenv("LLM_MODEL_REASONING", "gemini/gemini-2.5-pro")
LLM_MODEL_SUMMARY: Final[str] = os.getenv(
    "LLM_MODEL_SUMMARY", "gemini/gemini-pro"
)  # for paper summary

# Configure Vertex AI project/location if specified in environment
if os.getenv("VERTEX_PROJECT"):
    litellm.vertex_project = os.getenv("VERTEX_PROJECT")
if os.getenv("VERTEX_LOCATION"):
    litellm.vertex_location = os.getenv("VERTEX_LOCATION")


class LLMCall[T: BaseModel | str](Protocol):
    """This is essentially a union of `client.beta.chat.completions.parse` and `client.chat.completions.create`.

    Use `LLMCall[str]` as an equivalent to `client.chat.completions.create`.
    Use `LLMCall[BaseModel]` as an equivalent to `client.beta.chat.completions.parse`.

    In both cases, the return value is a `ParsedChatCompletionMessage[T]`. The `parsed` field will be `None` if `T` is `str`.
    """

    def __call__(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        response_format: type[T] | None = None,
        tools: Sequence[ChatCompletionToolParam] | None = None,
    ) -> ParsedChatCompletionMessage[T]: ...


class TypedLLMCall[T: BaseModel | str](Protocol):
    """Partial application of `LLMCall` that is fixed to use a particular response format, equivalent to `partial(llm, response_format=response_format)`."""

    def __call__(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        tools: Sequence[ChatCompletionToolParam] | None = None,
    ) -> ParsedChatCompletionMessage[T]: ...


def typed_call[T: BaseModel](
    llm: LLMCall[T], response_format: type[T]
) -> TypedLLMCall[T]:
    """Return a partial application of `llm` that is fixed to use the given response format, equivalent to `partial(llm, response_format=response_format)`."""
    return cast(TypedLLMCall[T], partial(llm, response_format=response_format))


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: Usage) -> Self:
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    @classmethod
    def from_litellm(cls, usage: litellm.Usage) -> Self:
        return Usage(
            prompt_tokens=usage.prompt_tokens or 0,
            completion_tokens=usage.completion_tokens or 0,
            total_tokens=usage.total_tokens or 0,
        )

    __add__ = add


@dataclass
class LLM:
    tokens: dict[str, Usage] = field(default_factory=partial(defaultdict, Usage))
    cost: dict[str, float] = field(default_factory=partial(defaultdict, float))

    @property
    def total_prompt_tokens(self) -> int:
        return sum(usage.prompt_tokens for usage in self.tokens.values())

    @property
    def total_completion_tokens(self) -> int:
        return sum(usage.completion_tokens for usage in self.tokens.values())

    @property
    def total_cost(self) -> float:
        return sum(self.cost.values())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(cost={self.total_cost}, prompt_tokens={self.total_prompt_tokens}, completion_tokens={self.total_completion_tokens})"

    @overload
    def completion[T: BaseModel](
        self,
        model: str,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        response_format: type[T],
        tools: Sequence[ChatCompletionToolParam] | None = None,
    ) -> ParsedChatCompletionMessage[T]: ...

    @overload
    def completion(
        self,
        model: str,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        response_format: None = None,
        tools: Sequence[ChatCompletionToolParam] | None = None,
    ) -> ParsedChatCompletionMessage[str]: ...

    def completion[T: BaseModel | str](
        self,
        model: str,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        response_format: type[T] | None = None,
        tools: Sequence[ChatCompletionToolParam] | None = None,
    ) -> ParsedChatCompletionMessage[T]:
        is_typed = response_format is not None
        provider_response_format = response_format if is_typed else None
        # Gemini currently rejects tool calling + application/json response_mime_type.
        # Fall back to local parsing when typed output is requested alongside tools.
        if is_typed and tools and (model.startswith("gemini/") or model.startswith("vertex_ai/")):
            provider_response_format = None
            logger.warning(
                f"Disabling provider response_format for {model} when tools are enabled; "
                "falling back to local JSON parsing."
            )
        prompt_tokens = litellm.token_counter(
            model=model,
            messages=messages,
            tools=tools,
        )
        try:
            prompt_cost = litellm.completion_cost(model=model, messages=messages)
        except Exception as e:  # model may be unmapped in litellm cost table
            logger.warning(f"Could not compute prompt cost for {model}: {e}")
            prompt_cost = 0.0
        with tlog.context(
            "llm_call",
            model=model,
            prompt_tokens=prompt_tokens,
            prompt_cost=prompt_cost,
            content=messages,
        ) as ctx:
            if prompt_cost + self.total_cost > MAX_COST:
                raise RuntimeError(
                    f"Cost limit exceeded: {prompt_cost + self.total_cost:.3f} > {MAX_COST:.3f}"
                )
            # print("MESSAGES:", json.dumps(list(messages)))
            # print("TOOLS:", json.dumps(tools))

            response = None
            for attempt in range(MAX_LLM_RETRIES):
                try:
                    response = completion_factory(model)(
                        model=model,
                        messages=list(messages),
                        tools=tools,
                        response_format=provider_response_format,
                    )
                    break
                except Exception as e:
                    error_text = str(e)
                    retriable = any(
                        marker in error_text
                        for marker in (
                            "RateLimitError",
                            "ServiceUnavailable",
                            '"code": 429',
                            '"code": 503',
                            "RESOURCE_EXHAUSTED",
                            "UNAVAILABLE",
                        )
                    )
                    is_last = attempt >= MAX_LLM_RETRIES - 1
                    if not retriable or is_last:
                        raise

                    # Parse server-suggested retry delay if present
                    delay_seconds = min(60, 2**attempt)
                    retry_match = re.search(r'"retryDelay":\s*"(\d+)', error_text)
                    if retry_match:
                        delay_seconds = int(retry_match.group(1)) + 5  # server delay + buffer
                    elif '429' in error_text or 'RESOURCE_EXHAUSTED' in error_text:
                        delay_seconds = max(delay_seconds, 40)  # min 40s for rate limits
                    first_line = (
                        error_text.splitlines()[0] if error_text else type(e).__name__
                    )
                    logger.warning(
                        f"Transient LLM error for {model} "
                        f"(attempt {attempt + 1}/{MAX_LLM_RETRIES}). "
                        f"Retrying in {delay_seconds}s. Error: {first_line}"
                    )
                    time.sleep(delay_seconds)

            if response is None:
                raise RuntimeError("LLM completion failed without a response.")
            message = response.choices[0].message
            try:
                completion_cost = litellm.completion_cost(response)
            except Exception as e:
                logger.warning(f"Could not compute completion cost: {e}")
                completion_cost = 0.0
            usage = Usage.from_litellm(response.usage)
            self.tokens[model] += usage
            self.cost[model] += completion_cost
            logger.debug(
                f"Called {model} with {usage.total_tokens} tokens for ${completion_cost:.3f} (total cost: ${self.total_cost:.3f})"
            )
            ctx.content = message.model_dump()
            ctx.update(
                cost=completion_cost,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                overall_cost=self.total_cost,
                overall_prompt_tokens=self.total_prompt_tokens,
                overall_completion_tokens=self.total_completion_tokens,
            )

        # Parse (if typed), and return
        if is_typed:
            message.refusal = None
            try:
                if provider_response_format is not None:
                    return (
                        parse_chat_completion(
                            response_format=cast(type[T], response_format),
                            chat_completion=response,
                            input_tools=tools or [],
                        )
                        .choices[0]
                        .message
                    )

                # Fallback path for providers/models that don't support typed
                # response format when tool calling is enabled.
                if message.tool_calls:
                    # Intermediate agent turns often return only tool calls.
                    # Keep parsed=None so the agent continues stepping.
                    return ParsedChatCompletionMessage(
                        **message.model_dump(),
                        parsed=None,
                    )

                content = message.content or ""
                parsed: T
                try:
                    parsed = cast(type[T], response_format).model_validate_json(content)
                except Exception:
                    match = re.search(r"\{[\s\S]*\}", content)
                    success = False
                    if match:
                        try:
                            parsed = cast(type[T], response_format).model_validate_json(
                                match.group(0)
                            )
                            success = True
                        except Exception:
                            pass
                    
                    if not success:
                        # Last-resort coercion call: ask the same model to
                        # convert free-form text to the required typed JSON.
                        schema = cast(type[T], response_format).model_json_schema()
                        coercion_messages: list[ChatCompletionMessageParam] = [
                            {
                                "role": "system",
                                "content": (
                                    "Convert the provided text into a valid JSON object "
                                    "that matches the provided schema. Return only JSON."
                                ),
                            },
                            {
                                "role": "user",
                                "content": f"Schema:\n{schema}\n\nText:\n{content}",
                            },
                        ]
                        coerced = completion_factory(model)(
                            model=model,
                            messages=coercion_messages,
                            tools=None,
                            response_format=response_format,
                        )
                        coerced_content = coerced.choices[0].message.content or ""
                        parsed = cast(type[T], response_format).model_validate_json(
                            coerced_content
                        )
                        if parsed is None:
                            raise RuntimeError(
                                "Expected JSON response for typed output, but none was found. "
                                f"Raw response: {content}"
                            )

                return ParsedChatCompletionMessage(
                    **message.model_dump(),
                    parsed=parsed,
                )
            except ValidationError as e:
                raise RuntimeError(
                    f"Validation error: {e}\n\nResponse: {message.content}"
                ) from e
        else:
            return ParsedChatCompletionMessage(
                **message.model_dump(), parsed=message.content
            )

    def for_model(self, model: str) -> LLMCall:
        """Return a partial application of `completion` that is fixed to use the given model."""
        return partial(self.completion, model=model)

    __getitem__ = for_model
