export type AddressSuggestion = {
  label: string;
  lat: number;
  lng: number;
};

type SuggestResponse = {
  enabled: boolean;
  suggestions: AddressSuggestion[];
};

export async function suggestAddresses(query: string, signal?: AbortSignal): Promise<SuggestResponse> {
  const response = await fetch(`/geocode/suggest?q=${encodeURIComponent(query)}`, { signal });

  if (!response.ok) {
    return { enabled: false, suggestions: [] };
  }

  return response.json();
}
