interface Config {
  NATS_SERVER_URL: string
  API_BASE_URL: string
  INTERACTEM_ADMIN_TOKEN: string
}

const config: Config = {
  NATS_SERVER_URL: import.meta.env.VITE_NATS_SERVER_URL,
  API_BASE_URL: import.meta.env.VITE_REACT_APP_API_BASE_URL,
  INTERACTEM_ADMIN_TOKEN: import.meta.env.VITE_INTERACTEM_ADMIN_TOKEN,
}

export default config
