import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/screen": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/geocode": "http://localhost:8000",
    },
  },
});
