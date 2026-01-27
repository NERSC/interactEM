import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { defineConfig } from "vite"

const __dirname = resolve()

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist_app",
    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
      },
    },
  },
})
