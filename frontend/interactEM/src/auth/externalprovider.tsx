import { createClient } from "@hey-api/client-axios"
import { CircularProgress } from "@mui/material"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  type LoginLoginWithExternalTokenResponse,
  client,
  loginLoginWithExternalToken,
} from "../client"
import { AUTH_QUERY_KEYS } from "../constants/tanstack"
import { AuthContext, type AuthProviderProps, type AuthState } from "./base"

class MissingExternalTokenError extends Error {
  constructor() {
    super("No external token available")
    this.name = "MissingExternalTokenError"
  }
}

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
  } = useQuery<
    LoginLoginWithExternalTokenResponse,
    MissingExternalTokenError | Error
  >({
    queryKey: AUTH_QUERY_KEYS.internalToken,
    queryFn: async () => {
      const externalToken = queryClient.getQueryData<string>(
        AUTH_QUERY_KEYS.externalToken,
      )

      if (!externalToken) {
        throw new MissingExternalTokenError()
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
    retry: (failureCount, error) => {
      console.log(`Retrying login attempt ${failureCount} after error:`, error)
      return failureCount < 3
    },
    retryDelay: (failureCount) => Math.min(1000 * 2 ** failureCount, 30000),
    enabled: !!queryClient.getQueryData(AUTH_QUERY_KEYS.externalToken),
  })

  if (isError) {
    console.error("Error during external auth:", error)
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
