from app.providers.openai import OpenAICompatibleAdapter


class CustomOpenAICompatibleAdapter(OpenAICompatibleAdapter):
    """A self-hosted server that speaks the Chat Completions API (e.g. a local model server).

    Only usable when ALLOW_CUSTOM_AI_ENDPOINTS is enabled.
    """

    slug = "custom"
    display_name = "Custom endpoint"
    default_base_url = None
    json_mode = "json_object"
    max_tokens_field = "max_tokens"
