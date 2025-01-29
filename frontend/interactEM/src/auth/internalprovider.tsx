import { client } from "../client"
import config from "../config"
import { AuthContext, type AuthProviderProps, type AuthState } from "./base"

export default function InternalAuthProvider({
  children,
  apiBaseUrl,
}: AuthProviderProps) {
  const value: AuthState = {
    token: config.INTERACTEM_ADMIN_TOKEN,
    isAuthenticated: true,
    isLoading: false,
    error: null,
  }

  client.setConfig({
    baseURL: apiBaseUrl,
    auth: config.INTERACTEM_ADMIN_TOKEN,
  })

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
