import { useEffect, useState } from "react";
import type { Memo } from "./api/types";
import { Button } from "./components/Button";
import { MemoDetailScreen } from "./screens/MemoDetailScreen";
import { NewSiteScreen } from "./screens/NewSiteScreen";

type Theme = "light" | "dark";
const THEME_STORAGE_KEY = "helios-theme";

function getStoredTheme(): Theme | null {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : null;
}

function DarkModeToggle() {
  // `explicit` is the visitor's persisted choice; until they toggle once,
  // the theme instead tracks the OS `prefers-color-scheme` media query (see colors.css).
  const [explicit, setExplicit] = useState<Theme | null>(() => getStoredTheme());
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
  );

  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mql.addEventListener("change", handleChange);
    return () => mql.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (explicit) {
      document.documentElement.setAttribute("data-theme", explicit);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, [explicit]);

  const dark = explicit ? explicit === "dark" : systemDark;

  const toggle = () => {
    const next: Theme = dark ? "light" : "dark";
    setExplicit(next);
    localStorage.setItem(THEME_STORAGE_KEY, next);
  };

  return (
    <div className="theme-toggle-wrap">
      <Button variant="ghost" size="sm" onClick={toggle}>
        {dark ? "Light mode" : "Dark mode"}
      </Button>
    </div>
  );
}

export default function App() {
  const [memo, setMemo] = useState<Memo | null>(null);

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-page)" }}>
      <DarkModeToggle />
      {memo ? (
        <MemoDetailScreen memo={memo} onBack={() => setMemo(null)} />
      ) : (
        <NewSiteScreen onComplete={setMemo} />
      )}
    </div>
  );
}
