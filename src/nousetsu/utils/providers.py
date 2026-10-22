"""Provider readiness shared by setup and production model creation."""
PROVIDER_KEYS = {
    "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY", "custom": "CUSTOM_API_KEY",
}


def usable_key(value: str | None) -> bool:
    token = (value or "").strip().lower()
    return bool(token) and not (token.startswith(("your_", "your-", "replace_", "replace-", "paste_", "<")) or token in {"changeme", "change-me", "placeholder"})


def provider_for_model(model: str, env=None) -> str:
    model = model.strip().lower()
    for provider in ("openai", "openrouter", "custom"):
        if model.startswith(provider + ":"):
            return provider
    if "gemini" in model or "gemma" in model:
        return "gemini"
    if "/" in model:
        if env is not None and model.startswith("openai/") and not provider_key("openrouter", env) and provider_key("openai", env):
            return "openai"
        return "openrouter"
    if env is not None and not provider_key("openai", env) and provider_key("openrouter", env):
        return "openrouter"
    return "openai"


def provider_key(provider: str, env) -> str:
    key = env.get(PROVIDER_KEYS[provider], "")
    if provider == "gemini" and not usable_key(key):
        key = env.get("GOOGLE_API_KEY", "")
    return key if usable_key(key) else ""


def model_ready(model: str, env) -> bool:
    if model.lower().startswith(("mock", "test")):
        return True
    provider = provider_for_model(model, env)
    if ":" in model and not model.split(":", 1)[-1].strip():
        return False
    return bool(model.strip() and provider_key(provider, env) and (provider != "custom" or env.get("CUSTOM_API_BASE_URL")))
