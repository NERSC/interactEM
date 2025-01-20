// TODO: Implement internal auth:

import { useQuery } from "@tanstack/react-query"
import { AUTH_QUERY_KEYS } from "../constants/tanstack"
import { AuthContext, type AuthState } from "./base"

export default function InternalAuthProvider({
  children,
}: { children: React.ReactNode }) {
  const {
    data: token,
    isSuccess,
    isLoading,
    error,
  } = useQuery({
    queryKey: AUTH_QUERY_KEYS.internalToken,
  })

  const value: AuthState = {
    token: token?.access_token ?? null,
    isAuthenticated: isSuccess,
    isLoading,
    error: error instanceof Error ? error : null,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
