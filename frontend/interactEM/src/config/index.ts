interface Config {
  NATS_SERVER_URL: string
  API_BASE_URL: string
  API_TOKEN: string
}

const config: Config = {
  NATS_SERVER_URL: import.meta.env.VITE_NATS_SERVER_URL,
  API_BASE_URL: import.meta.env.VITE_REACT_APP_API_BASE_URL,
  API_TOKEN: import.meta.env.VITE_REACT_APP_API_TOKEN,
}

export default config
