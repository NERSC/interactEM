import { createClient } from "@hey-api/client-axios"
import { CircularProgress } from "@mui/material"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { client, loginLoginWithExternalToken } from "../client"
import { AUTH_QUERY_KEYS } from "../constants/tanstack"
import { AuthContext, type AuthProviderProps, type AuthState } from "./base"

export default function ExternalAuthProvider({
  children,
  apiBaseUrl,
}: AuthProviderProps) {
  const queryClient = useQueryClient()

  const authClient = createClient({
    baseURL: apiBaseUrl,
  })

  const {
    data: token,
    isSuccess,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: AUTH_QUERY_KEYS.internalToken,
    queryFn: async () => {
      const externalToken = queryClient.getQueryData<string>(
        AUTH_QUERY_KEYS.externalToken,
      )

      if (!externalToken) {
        throw new Error("No external token available")
      }

      const { data: token, status } = await loginLoginWithExternalToken<true>({
        client: authClient,
        headers: { Authorization: `Bearer ${externalToken}` },
      })

      if (status >= 400) {
        throw new Error(
          `Failed to login with external token, status: ${status}`,
        )
      }

      return token
    },
    retry: 1,
    enabled: !!queryClient.getQueryData(AUTH_QUERY_KEYS.externalToken),
  })

  if (isError) {
    return <div>Authorization error</div>
  }

  if (isLoading || !isSuccess) {
    return (
      <div>
        <CircularProgress />
      </div>
    )
  }

  if (isSuccess) {
    client.setConfig({
      auth: token.access_token,
      baseURL: apiBaseUrl,
    })
  }

  const value: AuthState = {
    token: token?.access_token ?? null,
    natsJwt: token?.nats_jwt ?? null,
    isAuthenticated: isSuccess,
    isLoading,
    error: error ? error : null,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
