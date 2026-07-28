import { useEffect, useRef, useState } from "react";
import { suggestAddresses, type AddressSuggestion } from "../api/geocode";
import { Input } from "./Input";

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 3;

export function AddressAutocomplete({
  value,
  onChange,
  onEnter,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  onEnter?: () => void;
  error?: string;
}) {
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const abortRef = useRef<AbortController>();

  useEffect(() => {
    return () => {
      clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, []);

  const handleChange = (next: string) => {
    onChange(next);
    setOpen(false);

    clearTimeout(debounceRef.current);
    abortRef.current?.abort();

    if (!enabled || next.trim().length < MIN_QUERY_LENGTH) {
      setSuggestions([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const result = await suggestAddresses(next.trim(), controller.signal);
        setEnabled(result.enabled);
        setSuggestions(result.suggestions);
        setOpen(result.suggestions.length > 0);
      } catch {
        // Aborted or network error — degrade to plain input, no suggestions.
        setSuggestions([]);
      }
    }, DEBOUNCE_MS);
  };

  const selectSuggestion = (suggestion: AddressSuggestion) => {
    onChange(suggestion.label);
    setSuggestions([]);
    setOpen(false);
  };

  return (
    <div style={{ position: "relative" }}>
      <Input
        label="Address"
        placeholder="123 County Rd, Madison County, NY"
        value={value}
        onChange={handleChange}
        onEnter={onEnter}
        error={error}
      />
      {open && suggestions.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            marginTop: 4,
            background: "var(--surface-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-elevated)",
            zIndex: 10,
            overflow: "hidden",
          }}
        >
          {suggestions.map((s) => (
            <button
              key={`${s.label}-${s.lat}-${s.lng}`}
              type="button"
              onClick={() => selectSuggestion(s)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                background: "transparent",
                border: "none",
                padding: "8px 12px",
                cursor: "pointer",
                font: "var(--text-body-md)",
                color: "var(--text-primary)",
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
