import {
  type UseMutationResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import { z } from "zod"
import type { OperatorSpecParameter } from "../../client"
import {
  STREAM_PARAMETERS,
  SUBJECT_OPERATORS_PARAMETERS_UPDATE,
} from "../../constants/nats"
import { useNats } from "../../contexts/nats"
import { RuntimeOperatorParameterUpdateSchema } from "../../types/params"

export const useParameterUpdate = (
  operatorID: string,
  parameter: OperatorSpecParameter,
): UseMutationResult<void, Error, string> => {
  const { jetStreamClient } = useNats()
  const queryClient = useQueryClient()

  const updateParameter = async (value: string): Promise<void> => {
    if (!jetStreamClient) {
      throw new Error("No JetStream client available")
    }

    try {
      const updateData = RuntimeOperatorParameterUpdateSchema.parse({
        canonical_operator_id: operatorID,
        name: parameter.name,
        value: value,
      })
      const subject = `${SUBJECT_OPERATORS_PARAMETERS_UPDATE}.${operatorID}.${parameter.name}`
      const encoder = new TextEncoder()
      const payload = encoder.encode(JSON.stringify(updateData))
      await jetStreamClient.publish(subject, payload)
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.error("Parameter update validation failed:", error.errors)
        throw new Error(
          `Invalid parameter update data: ${error.errors.map((e) => e.message).join(", ")}`,
        )
      }
      console.error("Failed to publish parameter update:", error)
      throw error
    }
  }

  const mutation = useMutation({
    mutationFn: updateParameter,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [STREAM_PARAMETERS, operatorID, parameter.name],
      })
    },
  })

  return mutation
}
