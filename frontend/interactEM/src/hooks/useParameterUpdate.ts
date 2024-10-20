import {
  useMutation,
  type UseMutationResult,
  useQueryClient,
} from "@tanstack/react-query"
import { useNats } from "../nats/NatsContext"
import type { OperatorParameter } from "../operators"
import { PARAMETERS_QUERYKEY, PARAMETERS_STREAM } from "../constants/nats"

export const useParameterUpdate = (
  operatorID: string,
  parameter: OperatorParameter,
): UseMutationResult<void, Error, string> => {
  const { jetStreamClient, jc } = useNats()
  const queryClient = useQueryClient()

  const updateParameter = async (value: string): Promise<void> => {
    if (!jetStreamClient) {
      throw new Error("No JetStream client available")
    }

    try {
      const subject = `${PARAMETERS_STREAM}.${operatorID}`
      const payload = jc.encode({ [parameter.name]: value })
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
