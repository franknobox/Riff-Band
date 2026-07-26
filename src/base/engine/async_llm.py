import asyncio
import os
import re
import yaml

from openai import AsyncOpenAI

from pathlib import Path
from typing import Dict, Optional, Any
from base.engine.logs import logger, LogLevel



class LLMConfig:
    def __init__(self, config: dict):
        self.model = config.get("model", "gpt-4o-mini")
        self.temperature = config.get("temperature", 1)
        self.key = config.get("key", None)
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.top_p = config.get("top_p", 1)

class LLMsConfig:
    """Configuration manager for multiple LLM configurations"""
    
    _instance = None  # For singleton pattern if needed
    _default_config = None
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize with an optional configuration dictionary"""
        self.configs = config_dict or {}
    
    # 返回LLMsConfig类实例
    @classmethod
    def default(cls):
        """Get or create a default configuration — env vars take priority over YAML."""
        if cls._default_config is None:
            # 1. Try env vars (always takes priority)
            env_config = cls._load_config_from_env() or {}

            # 2. Try YAML files (fallback for models not in env)
            yaml_config: Dict[str, Any] = {}
            config_paths = [
                Path("config/model_config.yaml"),
                Path("config/global_config.yaml"),
                Path("config/global_config2.yaml"),
                Path("./config/global_config.yaml"),
            ]
            config_file = next(
                (path for path in config_paths if path.exists() and path.stat().st_size > 0),
                None,
            )
            if config_file is not None:
                with open(config_file, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                if "models" in raw:
                    yaml_config = raw["models"] or {}

            # 3. Merge: env vars override YAML for matching model names
            merged = {**yaml_config, **env_config}

            if not merged:
                raise FileNotFoundError(
                    "No LLM configuration found. Set AUTOENV_OPENAI_API_KEY in .env, "
                    "or create config/model_config.yaml."
                )

            cls._default_config = cls(merged)

        return cls._default_config

    # 没有YAML配置文件时，从环境变量构建配置的后备方法
    @classmethod
    def _load_config_from_env(cls) -> Optional[Dict[str, Any]]:
        """Build configuration from environment variables when no YAML file is present."""
        inline_config = os.getenv("AUTOENV_MODEL_CONFIG_JSON")
        if inline_config:
            try:
                data = yaml.safe_load(inline_config)
            except yaml.YAMLError:
                logger.log_to_file(
                    LogLevel.WARNING,
                    "Failed to parse AUTOENV_MODEL_CONFIG_JSON; falling back to explicit env vars.",
                )
            else:
                if isinstance(data, dict):
                    return data.get("models", data) or {}

        api_key = os.getenv("AUTOENV_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

        base_url = (
            os.getenv("AUTOENV_OPENAI_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )

        def _get_float(name: str, default: float) -> float:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return float(raw)
            except ValueError:
                logger.log_to_file(
                    LogLevel.WARNING,
                    f"Invalid float value for {name}: {raw!r}; using {default}.",
                )
                return default

        temperature = _get_float("AUTOENV_OPENAI_TEMPERATURE", 1)
        top_p = _get_float("AUTOENV_OPENAI_TOP_P", 1)

        models_env = os.getenv("AUTOENV_OPENAI_MODELS", "o3")
        models = [m.strip() for m in models_env.split(",") if m.strip()]

        if not models:
            models = ["o3"]

        config: Dict[str, Any] = {}
        for model_name in models:
            normalized = model_name.upper().replace('-','_').replace('/','_')
            env_key_name = f"AUTOENV_{normalized}_API_KEY"
            env_base_name = f"AUTOENV_{normalized}_BASE_URL"

            model_api_key = os.getenv(env_key_name) or api_key
            model_base_url = os.getenv(env_base_name, base_url)

            config[model_name] = {
                "api_key": model_api_key,
                "base_url": model_base_url,
                "temperature": temperature,
                "top_p": top_p,
            }

        return config if any(item.get("api_key") for item in config.values()) else None
    
    def get(self, llm_name: str) -> LLMConfig:
        """Get the configuration for a specific LLM by name"""
        if llm_name not in self.configs:
            raise ValueError(f"Configuration for {llm_name} not found")
        
        config = self.configs[llm_name]
        
        # Create a config dictionary with the expected keys for LLMConfig
        llm_config = {
            "model": llm_name,  # Use the key as the model name
            "temperature": config.get("temperature", 1),
            "key": config.get("api_key"),  # Map api_key to key
            "base_url": config.get("base_url", "https://oneapi.deepwisdom.ai/v1"),
            "top_p": config.get("top_p", 1)  # Add top_p parameter
        }
        
        # Create and return an LLMConfig instance with the specified configuration
        return LLMConfig(llm_config)
    
    def add_config(self, name: str, config: Dict[str, Any]) -> None:
        """Add or update a configuration"""
        self.configs[name] = config
    
    def get_all_names(self) -> list:
        """Get names of all available LLM configurations"""
        return list(self.configs.keys())
    
class ModelPricing:
    """Pricing information for different models in USD per 1K tokens"""
    PRICES = {
        # openai: https://platform.openai.com/docs/pricing
        # anthropic: https://docs.anthropic.com/en/docs/about-claude/pricing
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "o3": {"input": 0.002, "output": 0.008},
        "o3-mini": {"input": 0.0011, "output": 0.0044},
        "gpt-5": {"input": 0.00125, "output": 0.01},
        "gpt-5-mini": {"input":0.00025, "output": 0.002},
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "moonshotai/kimi-k2": {"input": 0.000296, "output": 0.001185}, 
        "deepseek/deepseek-chat-v3.1": {"input":0.00025 , "output":0.001},
        "deepseek-chat": {"input":0.00025 , "output":0.001},
        "deepseek-v3": {"input": 0.00025, "output": 0.001},
        "deepseek-v3.1": {"input": 0.00025, "output": 0.001},
        "deepseek-v3.2": {"input": 0.00025, "output": 0.001},
        "deepseek-r1": {"input": 0.00055, "output": 0.00219},
        "z-ai/glm-4.5": {"input": 0.00033, "output": 0.00132},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.01},
        "gemini-2.5-flash-lite": {"input": 0.0001, "output": 0.0004},
        "claude-4-sonnet": {"input": 0.003, "output": 0.015},
        "claude-4-5-sonnet": {"input": 0.003, "output": 0.015},  # same as claude-sonnet-4-5
        "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
        "claude-4-5-haiku": {"input": 0.00088, "output": 0.0044},
        "claude-4-sonnet-20250514": {"input": 0.003, "output": 0.015},
        "gemini-2.5-flash": {"input": 0.0003, "output": 0.00252},
        "gemini-3-flash-preview": {"input": 0.0005, "output": 0.003},
        "gemini-3-pro-preview": {"input": 0.002, "output": 0.004},
        "gemini-2.5-flash-image": {"input": 0.0003, "output": 0.03},
        "x-ai/grok-4-fast": {"input": 0.0002, "output": 0.0005}
    }


    @classmethod
    def get_price(cls, model_name, token_type):
        """Get the price per 1K tokens for a specific model and token type (input/output)"""
        # Try to find exact match first
        if model_name in cls.PRICES:
            return cls.PRICES[model_name][token_type]
        
        # Try to find a partial match (e.g., if model name contains version numbers)
        for key in cls.PRICES:
            if key in model_name:
                return cls.PRICES[key][token_type]
        
        # Return default pricing if no match found
        return 0

class TokenUsageTracker:
    """Tracks token usage and calculates costs"""
    def __init__(self, model: str = ""):
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0
        self.usage_history = []
    
    def add_usage(self, model, input_tokens, output_tokens):
        """Add token usage for a specific API call"""
        input_cost = (input_tokens / 1000) * ModelPricing.get_price(model, "input")
        output_cost = (output_tokens / 1000) * ModelPricing.get_price(model, "output")
        total_cost = input_cost + output_cost
        
        usage_record = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "prices": {
                "input_price": ModelPricing.get_price(model, "input"),
                "output_price": ModelPricing.get_price(model, "output")
            }
        }
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += total_cost
        self.usage_history.append(usage_record)
        
        return usage_record
    
    def get_summary(self):
        """Get a summary of token usage and costs"""
        return {
            "model": self.model,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost,
            "call_count": len(self.usage_history),
            "history": self.usage_history
        }

class AsyncLLM:
    def __init__(self, config, system_msg:str = None, max_completion_tokens:int = None):
        """
        Initialize the AsyncLLM with a configuration
        
        Args:
            config: Either an LLMConfig instance or a string representing the LLM name
                   If a string is provided, it will be looked up in the default configuration
            system_msg: Optional system message to include in all prompts
            max_tokens: Optional maximum number of tokens to generate
        """
        # 调用抽象方法完成配置加载，支持直接传入LLMConfig实例、配置字典，或LLM名称字符串
        if isinstance(config, str):
            llm_name = config
            config = LLMsConfig.default().get(llm_name)
        
        # At this point, config should be an LLMConfig instance
        self.config = config
        self.aclient = None
        self.gemini_client = None
        if self._is_gemini_model():
            try:
                from google import genai
            except Exception as exc:
                raise ImportError(
                    "Gemini model configured but google-genai is not installed."
                ) from exc
            self.gemini_client = genai.Client(api_key=self.config.key)
        else:
            self.aclient = AsyncOpenAI(api_key=self.config.key, base_url=self.config.base_url)
        self.sys_msg = system_msg
        self.usage_tracker = TokenUsageTracker(model=self.config.model)
        self.max_completion_tokens = max_completion_tokens

    def _is_gemini_model(self) -> bool:
        return "gemini" in self.config.model.lower()

    def _normalized_model_name(self) -> str:
        return self.config.model.lower()

    def _build_gemini_contents(self, prompt):
        if isinstance(prompt, str):
            if self.sys_msg:
                return f"System instruction:\n{self.sys_msg}\n\nUser request:\n{prompt}"
            return prompt

        contents = []
        if self.sys_msg:
            contents.append({"text": f"System instruction:\n{self.sys_msg}"})

        for part in prompt:
            if not isinstance(part, dict):
                contents.append({"text": str(part)})
                continue
            if part.get("type") == "text":
                contents.append({"text": str(part.get("text", ""))})
                continue
            if part.get("type") == "image_url":
                image_url = part.get("image_url", {})
                url = image_url.get("url", "") if isinstance(image_url, dict) else ""
                contents.append({"text": str(url)})
                continue
            contents.append({"text": str(part)})
        return contents

    def _extract_gemini_text(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text:
            return text

        candidates = getattr(response, "candidates", None) or []
        chunks = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)
        return "\n".join(chunks)

    def _extract_gemini_usage(self, response: Any) -> tuple[int, int]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return 0, 0
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        return input_tokens, output_tokens

    async def _call_gemini(self, prompt) -> str:
        if self.gemini_client is None:
            raise RuntimeError("Gemini client is not initialized.")

        contents = self._build_gemini_contents(prompt)
        model_name = self._normalized_model_name()
        response = await asyncio.to_thread(
            self.gemini_client.models.generate_content,
            model=model_name,
            contents=contents,
        )

        input_tokens, output_tokens = self._extract_gemini_usage(response)
        self.usage_tracker.add_usage(self.config.model, input_tokens, output_tokens)

        ret = self._extract_gemini_text(response)
        return ret
        
    def _build_messages(self, prompt):
        """Build the message list for an LLM call. Returns (messages, tokens_to_use)."""
        message = []
        if self.sys_msg is not None:
            message.append({"content": self.sys_msg, "role": "system"})

        if isinstance(prompt, str):
            message.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list):
            message.append({"role": "user", "content": prompt})
        else:
            raise ValueError(f"prompt must be str or list, got {type(prompt)}")

        return message

    def _create_kwargs(self, tokens_to_use):
        """Build kwargs for the API call based on model type."""
        is_claude = "claude" in self.config.model.lower()
        is_moonshot = "moonshot" in self.config.model.lower()
        sampling_params = (
            {"temperature": self.config.temperature}
            if is_claude or is_moonshot
            else {"temperature": self.config.temperature, "top_p": self.config.top_p}
        )
        kwargs = {"model": self.config.model, **sampling_params}

        if self.config.model == "gemini-3-flash-preview":
            kwargs["reasoning_effort"] = "high"

        if tokens_to_use is not None:
            if "o3" in self.config.model:
                kwargs["max_completion_tokens"] = tokens_to_use
            elif "o3" not in self.config.model:
                kwargs["max_tokens"] = tokens_to_use

        return kwargs

    async def __call__(self, prompt, max_tokens=None):
        """Send a prompt to the LLM. Accepts text (str) or multimodal payloads (list)."""
        if self._is_gemini_model():
            return await self._call_gemini(prompt)

        message = []
        if self.sys_msg is not None:
            message.append({
                "content": self.sys_msg,
                "role": "system"
            })

        # Support plain text prompts and multimodal payloads (list)
        if isinstance(prompt, str):
            message.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list):
            message.append({"role": "user", "content": prompt})
        else:
            raise ValueError(f"prompt must be str or list, got {type(prompt)}")

        # Prefer to use the max_tokens argument passed to the function; if it is None, use the instance variable.
        tokens_to_use = max_tokens if max_tokens is not None else self.max_completion_tokens

        kwargs = self._create_kwargs(tokens_to_use)
        response = await self.aclient.chat.completions.create(
            messages=message,
            **kwargs,
        )

        # Extract token usage from response
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        # Track token usage and calculate cost
        usage_record = self.usage_tracker.add_usage(
            self.config.model,
            input_tokens,
            output_tokens
        )

        # Report to global cost monitor if active
        # record_cost(self.config.model, input_tokens, output_tokens, usage_record["total_cost"])

        # Return text or multimodal content (API returns content as provided)
        ret = response.choices[0].message.content

        return ret

    async def stream_response(self, prompt, max_tokens=None):
        """Stream response chunks from the LLM. Yields text deltas."""
        if self._is_gemini_model():
            # Gemini streaming not yet supported; fall back to full response
            text = await self.__call__(prompt, max_tokens=max_tokens)
            yield text
            return

        messages = self._build_messages(prompt)
        tokens_to_use = max_tokens if max_tokens is not None else self.max_completion_tokens
        kwargs = self._create_kwargs(tokens_to_use)

        try:
            stream = await self.aclient.chat.completions.create(
                messages=messages,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception:
            # Fall back to non-streaming on error
            text = await self.__call__(prompt, max_tokens=max_tokens)
            yield text

    def get_usage_summary(self):
        """Get a summary of token usage and costs"""
        return self.usage_tracker.get_summary()

    async def generate_text_to_image(self, prompt: str) -> dict[str, Any]:
        """
        Text-to-image generation.

        Args:
            prompt: Text prompt for image generation

        Returns:
            {
                'success': bool,
                'image_base64': str | None,
                'prompt': str,
                'error': str | None
            }
        """
        try:
            response = await self(prompt)
            image_b64 = self._extract_image_from_response(response)

            if not image_b64:
                return {
                    "success": False,
                    "image_base64": None,
                    "prompt": prompt,
                    "error": "No image found in response",
                }

            return {
                "success": True,
                "image_base64": image_b64,
                "prompt": prompt,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "image_base64": None,
                "prompt": prompt,
                "error": str(e),
            }

    async def generate_image_to_image(
        self, prompt: str, reference_images: list[str]
    ) -> dict[str, Any]:
        """
        Image-to-image generation with style references.

        Args:
            prompt: Text prompt for image generation
            reference_images: List of base64-encoded reference images

        Returns:
            {
                'success': bool,
                'image_base64': str | None,
                'prompt': str,
                'error': str | None
            }
        """
        try:
            content = []
            for img_b64 in reference_images:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    }
                )
            content.append({"type": "text", "text": prompt})

            response = await self(content)
            image_b64 = self._extract_image_from_response(response)

            if not image_b64:
                return {
                    "success": False,
                    "image_base64": None,
                    "prompt": prompt,
                    "error": "No image found in response",
                }

            return {
                "success": True,
                "image_base64": image_b64,
                "prompt": prompt,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "image_base64": None,
                "prompt": prompt,
                "error": str(e),
            }

    def _extract_image_from_response(self, response: str) -> str | None:
        """Extract base64 image from LLM response."""
        if not isinstance(response, str):
            return None
        match = re.search(r"data:image/[^;]+;base64,([^)]+)", response)
        return match.group(1) if match else None


def create_llm_instance(llm_config) -> AsyncLLM:
    """
    Create an AsyncLLM instance using the provided configuration
    
    Args:
        llm_config: Either an LLMConfig instance, a dictionary of configuration values,
                            or a string representing the LLM name to look up in default config
    
    Returns:
        An instance of AsyncLLM configured according to the provided parameters
    """
    # Case 1: llm_config is already an LLMConfig instance
    if isinstance(llm_config, LLMConfig):
        return AsyncLLM(llm_config)
    
    # Case 2: llm_config is a string (LLM name)
    elif isinstance(llm_config, str):
        return AsyncLLM(llm_config)  # AsyncLLM constructor handles lookup
    
    # Case 3: llm_config is a dictionary
    elif isinstance(llm_config, dict):
        # Create an LLMConfig instance from the dictionary
        llm_config = LLMConfig(llm_config)
        return AsyncLLM(llm_config)
    
    else:
        raise TypeError("llm_config must be an LLMConfig instance, a string, or a dictionary")
