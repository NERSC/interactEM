import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { defineConfig } from "vite"
import dts from "vite-plugin-dts"
import { visualizer } from "rollup-plugin-visualizer"

const __dirname = resolve()

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    dts({
      rollupTypes: true,
      tsconfigPath: resolve(__dirname, "tsconfig.json"),
    }),
    visualizer({ open: true, filename: "bundle-visualization.html" }),
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
          // unsure if we need tanstack global...
        },
      },
      treeshake: true,
    },
  },
})
