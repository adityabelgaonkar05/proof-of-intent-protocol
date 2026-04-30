import json

import anthropic

from config.config import CLAUDE_API_KEY

_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """
You are an intent compiler for a DeFi transaction system.
Convert natural language instructions into a structured JSON intent object.
You must return ONLY valid JSON. No explanation. No markdown. No code blocks.
Be conservative: if an amount is ambiguous, use the lower bound.
If a protocol is not explicitly named, do not include it.

Output this exact schema:
{
  "tokenIn": "<ERC20 token symbol>",
  "tokenInAddress": "<checksummed address or null if unknown>",
  "maxAmountIn": <integer, in token units with decimals. USDC has 6 decimals so 500 USDC = 500000000>,
  "minAmountOut": <integer, minimum acceptable output in output token units>,
  "allowedProtocols": ["<protocol name>"],
  "deadlineMinutes": <integer, minutes from now>,
  "reasoning": "<one sentence explaining your interpretation>"
}

If you cannot parse the instruction into this schema, return:
{"error": "Cannot parse: <reason>"}
"""


def compile_intent(natural_language: str) -> dict:
    response = _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": natural_language}],
    )

    raw = response.content[0].text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid JSON: {raw!r}") from exc

    if "error" in parsed:
        raise ValueError(parsed["error"])

    return parsed


def display_intent(compiled: dict) -> None:
    print("\n--- Compiled Intent ---")
    print(f"  Token In:          {compiled.get('tokenIn', 'N/A')}")
    print(f"  Token In Address:  {compiled.get('tokenInAddress', 'N/A')}")
    print(f"  Max Amount In:     {compiled.get('maxAmountIn', 'N/A')}")
    print(f"  Min Amount Out:    {compiled.get('minAmountOut', 'N/A')}")
    print(f"  Allowed Protocols: {', '.join(compiled.get('allowedProtocols', []))}")
    print(f"  Deadline:          {compiled.get('deadlineMinutes', 'N/A')} minutes from now")
    print(f"  Reasoning:         {compiled.get('reasoning', 'N/A')}")
    print("-----------------------")
    print("PLEASE REVIEW THE ABOVE BEFORE SIGNING")


def interactive_compile() -> dict:
    print("Enter your intent in plain English:")
    natural_language = input("> ").strip()

    try:
        compiled = compile_intent(natural_language)
    except ValueError as exc:
        print(f"Error: {exc}")
        print("Let's try again.")
        return interactive_compile()

    display_intent(compiled)

    print("Does this match your intent? (yes/no):")
    answer = input("> ").strip().lower()

    if answer == "yes":
        return compiled

    print("Let's try again.")
    return interactive_compile()


if __name__ == "__main__":
    interactive_compile()
