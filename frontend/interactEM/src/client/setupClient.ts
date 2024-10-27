import { client } from "./index"

client.setConfig({
  baseURL:
    import.meta.env.VITE_REACT_APP_API_BASE_URL || "http://localhost:80/",
})

client.instance.interceptors.request.use((config) => {
  const token = import.meta.env.VITE_REACT_APP_API_TOKEN

  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`)
  }
  return config
})
