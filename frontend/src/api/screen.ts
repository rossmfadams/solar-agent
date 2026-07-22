import type { Memo, ScreenRequest } from "./types";

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
