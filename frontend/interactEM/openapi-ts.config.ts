import { defaultPlugins, defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "openapi.json",
  output: {
    format: "biome",
    path: "src/client/generated",
  },
  plugins: [
    ...defaultPlugins,
    "@hey-api/client-axios",
    "@tanstack/react-query",
    "zod",
  ],
})
