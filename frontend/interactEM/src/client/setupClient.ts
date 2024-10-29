import { client } from "./index"
import clientConfig from "../config"

client.setConfig({
  baseURL: clientConfig.API_BASE_URL || "http://localhost:80/",
})

client.instance.interceptors.request.use((config) => {
  const token = clientConfig.API_TOKEN

  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`)
  }
  return config
})
