import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { visualizer } from "rollup-plugin-visualizer"
import { defineConfig } from "vite"

const __dirname = resolve()

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    strictPort: true,
    port: 5173,
  },
  plugins: [
    react(),
    visualizer({ open: false, filename: "bundle-visualization.html" }),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      name: "InteractEM",
      fileName: "interactem",
    },
    rollupOptions: {
      // this is critical for react-query. TODO: figure out why...
      // https://github.com/TanStack/query/issues/7927
      // potentially explore https://www.npmjs.com/package/@tanstack/config
      external: ["react", "react-dom", "@tanstack/react-query"],
      output: {
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
          "@tanstack/react-query": "ReactQuery",
        },
      },
      treeshake: true,
    },
  },
})
