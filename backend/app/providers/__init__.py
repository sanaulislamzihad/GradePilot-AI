"""Provider registry: slug -> adapter class."""

from app.providers.base import ProviderAdapter
from app.providers.claude import ClaudeAdapter
from app.providers.custom import CustomOpenAICompatibleAdapter
from app.providers.deepseek import DeepSeekAdapter
from app.providers.gemini import GeminiAdapter
from app.providers.groq import GroqAdapter
from app.providers.openai import OpenAIAdapter
from app.providers.openrouter import OpenRouterAdapter

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    adapter.slug: adapter
    for adapter in (
        GeminiAdapter,
        OpenAIAdapter,
        ClaudeAdapter,
        DeepSeekAdapter,
        GroqAdapter,
        OpenRouterAdapter,
        CustomOpenAICompatibleAdapter,
    )
}
