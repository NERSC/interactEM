import {
  STREAM_PARAMETERS,
  SUBJECT_OPERATORS_PARAMETERS,
} from "../../constants/nats"
import type { RuntimeOperatorParameterAck } from "../../types/gen"
import { RuntimeOperatorParameterAckSchema } from "../../types/params"
import { useOperatorInSelectedPipeline } from "./useOperatorStatus"
import { useStreamMessage } from "./useStreamMessage"

export const useParameterAck = (
  operatorID: string,
  parameterName: string,
  defaultValue: string,
) => {
  const subject = `${SUBJECT_OPERATORS_PARAMETERS}.${operatorID}.${parameterName}`
  const { isInRunningPipeline } = useOperatorInSelectedPipeline(operatorID)

  const { data, hasReceivedMessage } =
    useStreamMessage<RuntimeOperatorParameterAck>({
      streamName: STREAM_PARAMETERS,
      subject,
      initialValue: null,
      enabled: isInRunningPipeline,
      transform: (unvalidated: any) => {
        try {
          // Validate
          const data = RuntimeOperatorParameterAckSchema.parse(unvalidated)

          // Check if the ack is for the correct operator/parameter
          if (
            data.canonical_operator_id !== operatorID ||
            data.name !== parameterName
          ) {
            console.warn(
              `Received ack for wrong parameter: expected ${operatorID}.${parameterName}, got ${data.canonical_operator_id}.${data.name}`,
            )
            return null
          }

          return data
        } catch (error) {
          console.error(
            `Failed to parse parameter ack for ${operatorID}.${parameterName}:`,
            error,
          )
          return null
        }
      },
    })

  // Return defaults if not in running pipeline
  const actualValue = isInRunningPipeline
    ? (data?.value ?? defaultValue)
    : defaultValue
  return {
    actualValue,
    hasReceivedMessage: isInRunningPipeline ? hasReceivedMessage : false,
    ackData: isInRunningPipeline ? data : null,
  }
}
