import { type QueryClient, useQueryClient } from "@tanstack/react-query"

export function useQueryClientContext(): QueryClient {
  const queryClient = useQueryClient()

  if (!queryClient) {
    throw new Error(
      "useQueryClientContext must be used within a QueryClientProvider",
    )
  }

  return queryClient
}
