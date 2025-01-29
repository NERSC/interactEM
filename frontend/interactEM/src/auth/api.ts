import { QueryClient } from "@tanstack/react-query"
import { AUTH_QUERY_KEYS } from "../constants/tanstack"

const queryClient = new QueryClient()

type LoginResult = {
  success: boolean
  error?: Error
}

export async function loginInteractem(
  external_token: string,
): Promise<LoginResult> {
  try {
    queryClient.setQueryData(AUTH_QUERY_KEYS.externalToken, external_token)
    // Trigger a refresh of the internal auth
    await queryClient.invalidateQueries({
      queryKey: AUTH_QUERY_KEYS.internalToken,
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to login to InteractEM:", error)
    return {
      success: false,
      error:
        error instanceof Error ? error : new Error("Unknown error occurred"),
    }
  }
}

// We want to use the interactemQueryClient since we cannot use useQueryClient()
// outside of a component (i.e., inside of the async function that we want to call)
export { queryClient as interactemQueryClient }
