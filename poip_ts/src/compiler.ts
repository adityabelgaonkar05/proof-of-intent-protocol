/** compile_intent — translate natural language into a structured intent dict. */

const CLAUDE_DEFAULT = 'claude-haiku-4-5-20251001';
const OPENAI_DEFAULT = 'gpt-5-mini';

export interface CompiledIntent {
  tokenIn: string;
  maxAmountIn: bigint;
  minAmountOut: bigint;
  allowedProtocols: string[];
  /** Unix timestamp */
  deadline: number;
}

const SYSTEM_PROMPT =
  'You are an intent compiler for a DeFi protocol. ' +
  'Translate the user\'s natural-language swap request into JSON with exactly these keys: ' +
  'token_in (ERC20 address), max_amount_in (integer raw units), ' +
  'min_amount_out (integer raw units), allowed_protocols (list of protocol name strings ' +
  'e.g. ["Uniswap-V3"]), deadline (Unix timestamp integer). ' +
  'Respond with valid JSON only, no explanation.';

/**
 * Translate natural language into structured intent parameters.
 *
 * Reads CLAUDE_API_KEY (preferred) or OPENAI_API_KEY from the environment.
 * Set MODEL env var to override the default model ID for whichever provider
 * is selected (defaults: claude-haiku-4-5-20251001 / gpt-5-mini).
 */
export async function compileIntent(
  naturalLanguage: string,
  options?: { apiKey?: string; useClaude?: boolean },
): Promise<CompiledIntent> {
  const claudeKey = options?.apiKey ?? process.env['CLAUDE_API_KEY'];
  const openaiKey = process.env['OPENAI_API_KEY'];
  const useClaude = (options?.useClaude ?? true) && Boolean(claudeKey);
  const apiKey = claudeKey ?? openaiKey;

  if (!apiKey) {
    throw new Error(
      'compileIntent() requires CLAUDE_API_KEY or OPENAI_API_KEY in the environment.',
    );
  }

  let raw: string;

  if (useClaude) {
    const model = process.env['MODEL'] ?? CLAUDE_DEFAULT;
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model,
        max_tokens: 512,
        system: SYSTEM_PROMPT,
        messages: [{ role: 'user', content: naturalLanguage }],
      }),
    });
    if (!res.ok) throw new Error(`Anthropic API ${res.status}: ${await res.text()}`);
    const data = (await res.json()) as { content: Array<{ type: string; text: string }> };
    raw = data.content[0]?.text ?? '';
  } else {
    const model = process.env['MODEL'] ?? OPENAI_DEFAULT;
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model,
        max_tokens: 512,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: naturalLanguage },
        ],
      }),
    });
    if (!res.ok) throw new Error(`OpenAI API ${res.status}: ${await res.text()}`);
    const data = (await res.json()) as { choices: Array<{ message: { content: string } }> };
    raw = data.choices[0]?.message.content ?? '';
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    throw new Error(`Model returned non-JSON output: ${raw}`);
  }

  return {
    tokenIn: String(parsed['token_in'] ?? ''),
    maxAmountIn: BigInt(String(parsed['max_amount_in'] ?? '0')),
    minAmountOut: BigInt(String(parsed['min_amount_out'] ?? '0')),
    allowedProtocols: (parsed['allowed_protocols'] as string[]) ?? [],
    deadline: Number(parsed['deadline'] ?? 0),
  };
}
