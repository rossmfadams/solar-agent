import type { Memo, ScreenRequest, ScreenStreamEvent } from "./types";

export async function getScreenMemo(siteId: string): Promise<Memo> {
  const response = await fetch(`/screen/${siteId}/memo`);

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Memo request failed (${response.status})`);
  }

  return response.json();
}

export async function postScreen(request: ScreenRequest): Promise<Memo> {
  const response = await fetch("/screen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Screen request failed (${response.status})`);
  }

  return response.json();
}

// Reads a text/event-stream response body, splitting on the blank-line
// delimiter between SSE frames and invoking onEvent for each parsed payload.
export async function streamScreen(
  request: ScreenRequest,
  onEvent: (event: ScreenStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/screen/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Screen stream failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      onEvent(JSON.parse(line.slice("data: ".length)) as ScreenStreamEvent);
    }
  }
}
