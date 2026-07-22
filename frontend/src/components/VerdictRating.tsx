function bandFor(score: number) {
  if (score >= 86) return { stars: 5, label: "Strong" };
  if (score >= 71) return { stars: 4, label: "Good" };
  if (score >= 51) return { stars: 3, label: "Moderate" };
  if (score >= 26) return { stars: 2, label: "Low" };
  if (score >= 1) return { stars: 1, label: "Very Low" };
  return { stars: 0, label: "Hard Disqualified" };
}

export function VerdictRating({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const { stars, label } = bandFor(score);
  const starSize = size === "lg" ? 22 : size === "sm" ? 14 : 18;
  const filled = "var(--accent)";
  const empty = "var(--border-subtle)";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", fontFamily: "var(--font-ui)" }}>
      <div style={{ font: `600 ${starSize}px var(--font-display)`, letterSpacing: 2, lineHeight: 1 }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} style={{ color: i <= stars ? filled : empty }}>
            ★
          </span>
        ))}
      </div>
      <div style={{ font: "var(--text-label-md)", color: "var(--accent-on-soft)", marginTop: 4 }}>
        {label} · {score}
      </div>
    </div>
  );
}
