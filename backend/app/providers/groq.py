from app.providers.openai import OpenAICompatibleAdapter


class GroqAdapter(OpenAICompatibleAdapter):
    slug = "groq"
    display_name = "Groq"
    default_base_url = "https://api.groq.com/openai/v1"
    json_mode = "json_object"
    max_tokens_field = "max_completion_tokens"
