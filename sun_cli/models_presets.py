"""Model presets for Sun CLI - flagship models from major providers."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class ModelPreset:
    """Model preset configuration."""
    name: str
    provider: str
    model_id: str
    base_url: str
    description: str
    context_length: str
    pricing: str


# Model presets organized by provider
MODEL_PRESETS: dict[str, list[ModelPreset]] = {
    "OpenAI": [
        ModelPreset(
            name="GPT-4o",
            provider="OpenAI",
            model_id="gpt-4o",
            base_url="https://api.openai.com/v1",
            description="OpenAI's most capable model",
            context_length="128K",
            pricing="$5/1M input, $15/1M output"
        ),
        ModelPreset(
            name="GPT-4o-mini",
            provider="OpenAI",
            model_id="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            description="Fast and cost-effective",
            context_length="128K",
            pricing="$0.15/1M input, $0.60/1M output"
        ),
    ],
    "Anthropic": [
        ModelPreset(
            name="Claude 3.5 Sonnet",
            provider="Anthropic",
            model_id="claude-3-5-sonnet-20241022",
            base_url="https://api.anthropic.com/v1",
            description="Balanced performance and speed",
            context_length="200K",
            pricing="$3/1M input, $15/1M output"
        ),
        ModelPreset(
            name="Claude 3 Opus",
            provider="Anthropic",
            model_id="claude-3-opus-20240229",
            base_url="https://api.anthropic.com/v1",
            description="Most capable model",
            context_length="200K",
            pricing="$15/1M input, $75/1M output"
        ),
    ],
    "Google": [
        ModelPreset(
            name="Gemini 2.0 Pro",
            provider="Google",
            model_id="gemini-2.0-pro-exp-02-05",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            description="Google's flagship model",
            context_length="1M",
            pricing="Free tier available"
        ),
    ],
    "Kimi (Moonshot)": [
        ModelPreset(
            name="Moonshot-v1-128k",
            provider="Kimi",
            model_id="moonshot-v1-128k",
            base_url="https://api.moonshot.cn/v1",
            description="Long context, Chinese optimized",
            context_length="128K",
            pricing="¥12/1M tokens"
        ),
        ModelPreset(
            name="Moonshot-v1-32k",
            provider="Kimi",
            model_id="moonshot-v1-32k",
            base_url="https://api.moonshot.cn/v1",
            description="Fast response",
            context_length="32K",
            pricing="¥12/1M tokens"
        ),
    ],
    "通义千问": [
        ModelPreset(
            name="Qwen-Max",
            provider="通义千问",
            model_id="qwen-max",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            description="Most capable model",
            context_length="32K",
            pricing="¥20/1M tokens"
        ),
        ModelPreset(
            name="Qwen-Plus",
            provider="通义千问",
            model_id="qwen-plus",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            description="Balanced performance",
            context_length="32K",
            pricing="¥4/1M tokens"
        ),
        ModelPreset(
            name="Qwen-Turbo",
            provider="通义千问",
            model_id="qwen-turbo",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            description="Fast and cost-effective",
            context_length="8K",
            pricing="¥0.8/1M tokens"
        ),
    ],
    "智谱 AI (GLM)": [
        ModelPreset(
            name="GLM-4-Plus",
            provider="智谱 AI",
            model_id="glm-4-plus",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            description="Enhanced capabilities",
            context_length="128K",
            pricing="¥5/1M tokens"
        ),
        ModelPreset(
            name="GLM-4",
            provider="智谱 AI",
            model_id="glm-4",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            description="Flagship model",
            context_length="128K",
            pricing="¥10/1M tokens"
        ),
        ModelPreset(
            name="GLM-4-Air",
            provider="智谱 AI",
            model_id="glm-4-air",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            description="Fast and lightweight",
            context_length="128K",
            pricing="¥1/1M tokens"
        ),
    ],
    "DeepSeek": [
        ModelPreset(
            name="DeepSeek-V3",
            provider="DeepSeek",
            model_id="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            description="Reasoning capabilities",
            context_length="64K",
            pricing="¥1/1M tokens (input), ¥2/1M tokens (output)"
        ),
        ModelPreset(
            name="DeepSeek-R1",
            provider="DeepSeek",
            model_id="deepseek-reasoner",
            base_url="https://api.deepseek.com/v1",
            description="Advanced reasoning",
            context_length="64K",
            pricing="¥4/1M tokens (input), ¥16/1M tokens (output)"
        ),
    ],
}


def get_all_presets() -> list[ModelPreset]:
    """Get all model presets as a flat list."""
    presets = []
    for provider_models in MODEL_PRESETS.values():
        presets.extend(provider_models)
    return presets


def get_preset_by_model_id(model_id: str) -> ModelPreset | None:
    """Get preset by model ID."""
    for preset in get_all_presets():
        if preset.model_id == model_id:
            return preset
    return None


def get_presets_by_provider(provider: str) -> list[ModelPreset]:
    """Get presets by provider name."""
    return MODEL_PRESETS.get(provider, [])


def get_provider_names() -> list[str]:
    """Get all provider names."""
    return list(MODEL_PRESETS.keys())
