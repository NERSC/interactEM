interface Config {
  NATS_SERVER_URL: string
  API_BASE_URL: string
}

const stripTrailingSlash = (value: string) => value.replace(/\/+$/, "")

function buildConfig(): Config {
  // Use .env.development variables in development
  if (import.meta.env.DEV) {
    return {
      NATS_SERVER_URL: import.meta.env.VITE_NATS_SERVER_URL || "",
      API_BASE_URL: stripTrailingSlash(
        import.meta.env.VITE_REACT_APP_API_BASE_URL || "",
      ),
    }
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
  const host = window.location.host

  return {
    NATS_SERVER_URL: `${protocol}//${host}/nats`,
    API_BASE_URL: stripTrailingSlash(`${window.location.protocol}//${host}/`),
  }
}

const config: Config = buildConfig()

export default config
