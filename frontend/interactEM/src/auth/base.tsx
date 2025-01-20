import { createContext, useContext } from "react"

// Both internal/external auth implement this
export type AuthState = {
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: Error | null
}

export const AuthContext = createContext<AuthState | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
