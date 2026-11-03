"""Provider names. Model allowlists and limits come from settings (.env)."""

PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDERS = (PROVIDER_GEMINI, PROVIDER_OPENAI)
# QueryLab's shared key only; users do not save Groq keys, so it is not in PROVIDERS.
PROVIDER_GROQ = "groq"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# OpenAI reasoning models spend part of the token budget thinking. With a small
# budget they can think all of it away and return no text, so they think as
# little as possible and get room. These describe the vendor API, not limits.
OPENAI_REASONING_MODEL_PREFIX = "gpt-5"
OPENAI_REASONING_EFFORT = "minimal"
OPENAI_REASONING_TOKEN_FACTOR = 4

# Gemini 2.5 Pro cannot switch thinking off; this is the smallest budget it accepts.
GEMINI_PRO_MIN_THINKING_BUDGET = 128
