import { client } from "./index"

client.setConfig({
  baseURL: "http://localhost:80/",
})

client.instance.interceptors.request.use((config) => {
  config.headers.set(
    "Authorization",
    "Bearer <TOKEN HERE>",
  )
  return config
})
