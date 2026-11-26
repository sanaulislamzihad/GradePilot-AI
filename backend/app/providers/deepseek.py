from app.providers.openai import OpenAICompatibleAdapter


class DeepSeekAdapter(OpenAICompatibleAdapter):
    slug = "deepseek"
    display_name = "DeepSeek"
    default_base_url = "https://api.deepseek.com/v1"
    # DeepSeek supports JSON object mode but not strict JSON Schema.
    json_mode = "json_object"
    max_tokens_field = "max_tokens"
