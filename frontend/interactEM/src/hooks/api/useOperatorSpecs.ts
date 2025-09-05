import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { operatorsReadOperatorsOptions } from "../../client"
import { zOperatorSpecs } from "../../client/generated/zod.gen"

export const useOperatorSpecs = () => {
  const queryClient = useQueryClient()
  const operatorsQuery = useQuery({
    ...operatorsReadOperatorsOptions(),
  })

  // Mutation to handle explicit refresh
  const refreshMutation = useMutation({
    mutationFn: () => {
      return queryClient.fetchQuery({
        ...operatorsReadOperatorsOptions({
          query: { refresh: true },
        }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: operatorsReadOperatorsOptions().queryKey,
      })
    },
  })

  const response = zOperatorSpecs.safeParse(operatorsQuery.data)
  const operatorSpecs = response.data?.data

  return {
    operatorSpecs,
    isRefreshing: refreshMutation.isPending,
    isLoading: operatorsQuery.isLoading,
    refetch: () => refreshMutation.mutate(),
  }
}

export default useOperatorSpecs
