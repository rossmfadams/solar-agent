export function MapPanel({ url, height = 320 }: { url: string; height?: number }) {
  return (
    <div
      style={{
        height,
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
        border: "1px solid var(--border-default)",
      }}
    >
      <iframe
        src={url}
        title="Site map"
        loading="lazy"
        sandbox="allow-scripts allow-same-origin"
        style={{ width: "100%", height: "100%", border: "none" }}
      />
    </div>
  );
}
