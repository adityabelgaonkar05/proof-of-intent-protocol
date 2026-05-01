"""compile_intent — translate natural language into a structured intent dict."""
import os


def compile_intent(
    natural_language: str,
    *,
    api_key: str | None = None,
    use_claude: bool = True,
) -> dict:
    """Translate *natural_language* into structured intent parameters.

    Requires either CLAUDE_API_KEY (default) or OPENAI_API_KEY in the
    environment, or pass *api_key* directly.

    Returns a dict with keys: token_in, max_amount_in, min_amount_out,
    allowed_protocols, deadline.
    """
    _api_key = api_key or os.getenv("CLAUDE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not _api_key:
        raise EnvironmentError(
            "compile_intent() requires CLAUDE_API_KEY (or OPENAI_API_KEY) in the "
            "environment, or pass api_key= directly."
        )

    _use_claude = use_claude and bool(os.getenv("CLAUDE_API_KEY") or api_key)

    _system = (
        "You are an intent compiler for a DeFi protocol. "
        "Translate the user's natural-language swap request into JSON with exactly these keys: "
        "token_in (ERC20 address), max_amount_in (integer raw units), "
        "min_amount_out (integer raw units), allowed_protocols (list of protocol name strings "
        "e.g. ['Uniswap-V3']), deadline (Unix timestamp integer). "
        "Respond with valid JSON only, no explanation."
    )

    if _use_claude:
        import anthropic  # noqa: PLC0415
        client = anthropic.Anthropic(api_key=_api_key)
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=512,
            system=_system,
            messages=[{"role": "user", "content": natural_language}],
        )
        raw = message.content[0].text
    else:
        import openai  # noqa: PLC0415
        client = openai.OpenAI(api_key=_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _system},
                {"role": "user",   "content": natural_language},
            ],
            max_tokens=512,
        )
        raw = response.choices[0].message.content or ""

    import json  # noqa: PLC0415
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned non-JSON output: {raw!r}") from exc
