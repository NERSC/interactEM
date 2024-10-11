import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  client: "@hey-api/client-axios",
  input: "openapi.json",
  output: {
    format: "biome",
    path: "src/client",
  },
  plugins: ["@tanstack/react-query"],
})
