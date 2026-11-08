import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

const BACKEND = process.env.STANDIN_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "聊天",
        short_name: "聊天",
        description: "只给一个人用的聊天",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#f2e9eb",
        theme_color: "#f2e9eb",
        lang: "zh-CN",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable"
          }
        ]
      },
      workbox: {
        navigateFallback: "/",
        globPatterns: ["**/*.{js,css,html,svg,png,webmanifest}"],
        cleanupOutdatedCaches: true
      }
    })
  ],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": BACKEND,
      "/c": BACKEND,
      "/healthz": BACKEND
    }
  }
});
