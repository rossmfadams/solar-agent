import { useState } from "react";
import type { Memo } from "./api/types";
import { Button } from "./components/Button";
import { MemoDetailScreen } from "./screens/MemoDetailScreen";
import { NewSiteScreen } from "./screens/NewSiteScreen";

function DarkModeToggle() {
  const [dark, setDark] = useState(false);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.setAttribute("data-theme", next ? "dark" : "light");
  };

  return (
    <div style={{ position: "fixed", top: 16, right: 16 }}>
      <Button variant="ghost" size="sm" onClick={toggle}>
        {dark ? "Light mode" : "Dark mode"}
      </Button>
    </div>
  );
}

export default function App() {
  const [memo, setMemo] = useState<Memo | null>(null);

  return (
    <div style={{ minHeight: "100vh", display: "flex", background: "var(--bg-page)" }}>
      <DarkModeToggle />
      {memo ? (
        <MemoDetailScreen memo={memo} onBack={() => setMemo(null)} />
      ) : (
        <NewSiteScreen onComplete={setMemo} />
      )}
    </div>
  );
}
