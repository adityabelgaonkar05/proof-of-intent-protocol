/**
 * TypeScript wrapper over the AXL node's local HTTP API.
 * Mirrors utils/axl_client.py — each agent runs its own node on a distinct port.
 *
 * Endpoints:
 *   GET  /topology  → { our_public_key: string, ... }
 *   POST /send      → header X-Destination-Peer-Id, body JSON bytes
 *   GET  /recv      → 204 empty | 200 message + X-From-Peer-Id header
 */

const API = (port: number) => `http://127.0.0.1:${port}`;

export async function getPublicKey(port: number): Promise<string> {
  const res = await fetch(`${API(port)}/topology`);
  if (!res.ok) throw new Error(`/topology ${res.status}`);
  const data = (await res.json()) as { our_public_key: string };
  return data.our_public_key;
}

export async function sendMessage(
  toPubkey: string,
  message: unknown,
  fromPort: number,
  retries = 8,
): Promise<void> {
  const body = JSON.stringify(message);
  let lastErr: unknown;
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${API(fromPort)}/send`, {
        method: 'POST',
        headers: {
          'X-Destination-Peer-Id': toPubkey,
          'Content-Type': 'application/octet-stream',
        },
        body,
      });
      if (res.status === 200) return;
      if (res.status === 502 || res.status === 503) {
        await sleep((i + 1) * 1000);
        continue;
      }
      throw new Error(`AXL /send returned ${res.status}`);
    } catch (err) {
      lastErr = err;
      if (i < retries - 1) await sleep((i + 1) * 1000);
    }
  }
  throw lastErr ?? new Error('AXL send failed after retries');
}

export async function listenForMessage(
  timeoutMs: number,
  port: number,
  pollMs = 200,
): Promise<{ from: string; message: unknown }> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${API(port)}/recv`);
      if (res.status === 204) {
        await sleep(pollMs);
        continue;
      }
      if (res.status === 200) {
        const message = (await res.json()) as unknown;
        const from = res.headers.get('X-From-Peer-Id') ?? '';
        return { from, message };
      }
      await sleep(pollMs);
    } catch {
      await sleep(pollMs);
    }
  }
  throw new Error(`AXL timeout on port ${port} after ${timeoutMs}ms`);
}

/**
 * Poll until a message with the expected type arrives.
 * Silently discards any message with a different type.
 */
export async function waitForType<T>(
  expectedType: string,
  port: number,
  timeoutMs: number,
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const remaining = deadline - Date.now();
      if (remaining <= 0) break;
      const { message } = await listenForMessage(Math.min(30_000, remaining), port);
      const msg = message as Record<string, unknown>;
      if (msg['type'] === expectedType) return message as T;
    } catch {
      // inner timeout — continue if outer deadline not reached
    }
  }
  throw new Error(`Timeout waiting for '${expectedType}' on port ${port}`);
}

/**
 * Poll until a message matching one of the given types arrives.
 */
export async function waitForAny<T>(
  types: string[],
  port: number,
  timeoutMs: number,
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const remaining = deadline - Date.now();
      if (remaining <= 0) break;
      const { message } = await listenForMessage(Math.min(30_000, remaining), port);
      const msg = message as Record<string, unknown>;
      if (types.includes(msg['type'] as string)) return message as T;
    } catch {
      // inner timeout — continue
    }
  }
  throw new Error(`Timeout waiting for [${types.join('|')}] on port ${port}`);
}

export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
