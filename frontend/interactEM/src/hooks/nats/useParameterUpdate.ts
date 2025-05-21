import {
  type UseMutationResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import type { OperatorParameter } from "../../client"
import { PARAMETERS_QUERYKEY, PARAMETERS_STREAM } from "../../constants/nats"
import { useNats } from "../../contexts/nats"

export const useParameterUpdate = (
  operatorID: string,
  parameter: OperatorParameter,
): UseMutationResult<void, Error, string> => {
  const { jetStreamClient } = useNats()
  const queryClient = useQueryClient()

  const updateParameter = async (value: string): Promise<void> => {
    if (!jetStreamClient) {
      throw new Error("No JetStream client available")
    }

    try {
      const subject = `${PARAMETERS_STREAM}.${operatorID}.${parameter.name}`
      const encoder = new TextEncoder()
      const payload = encoder.encode(
        JSON.stringify({ [parameter.name]: value }),
      )
      await jetStreamClient.publish(subject, payload)
    } catch (error) {
      console.error("Failed to publish set point:", error)
      throw error
    }
  }

  const mutation = useMutation({
    mutationFn: updateParameter,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [PARAMETERS_QUERYKEY, operatorID, parameter.name],
      })
    },
  })

  return mutation
}
