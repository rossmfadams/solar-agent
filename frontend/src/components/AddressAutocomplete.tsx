import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { suggestAddresses, type AddressSuggestion } from "../api/geocode";
import { Input } from "./Input";

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 3;
const LISTBOX_ID = "address-suggestions";

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
  const [highlighted, setHighlighted] = useState(-1);
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
    setHighlighted(-1);

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
    setHighlighted(-1);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((i) => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === "Enter" && highlighted >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[highlighted]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setHighlighted(-1);
    }
  };

  return (
    <div style={{ position: "relative" }}>
      <Input
        id="site-address"
        label="Address"
        placeholder="123 County Rd, Madison County, NY"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onEnter={onEnter}
        error={error}
        role="combobox"
        ariaExpanded={open && suggestions.length > 0}
        ariaControls={LISTBOX_ID}
        ariaActiveDescendant={highlighted >= 0 ? `address-option-${highlighted}` : undefined}
        ariaAutoComplete="list"
      />
      {open && suggestions.length > 0 && (
        <div
          id={LISTBOX_ID}
          role="listbox"
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
          {suggestions.map((s, i) => (
            <div
              key={`${s.label}-${s.lat}-${s.lng}`}
              id={`address-option-${i}`}
              role="option"
              aria-selected={highlighted === i}
              tabIndex={-1}
              className="tap-target-block"
              onMouseEnter={() => setHighlighted(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                selectSuggestion(s);
              }}
              style={{
                textAlign: "left",
                background: highlighted === i ? "var(--surface-accent-soft)" : "transparent",
                padding: "8px 12px",
                cursor: "pointer",
                font: "var(--text-body-md)",
                color: "var(--text-primary)",
              }}
            >
              {s.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
