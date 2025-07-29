import {
  STREAM_PARAMETERS,
  SUBJECT_OPERATORS_PARAMETERS,
} from "../../constants/nats"
import {
  type RuntimeOperatorParameterAck,
} from "../../types/gen"
import { RuntimeOperatorParameterAckSchema } from "../../types/params"
import { useStreamMessage } from "./useStreamMessage"

const streamConfig = {
  name: STREAM_PARAMETERS,
  subjects: [`${STREAM_PARAMETERS}.>`],
}

export const useParameterAck = (
  operatorID: string,
  parameterName: string,
  defaultValue: string,
) => {
  const subject = `${SUBJECT_OPERATORS_PARAMETERS}.${operatorID}.${parameterName}`

  const { data, hasReceivedMessage } =
    useStreamMessage<RuntimeOperatorParameterAck>({
      streamName: STREAM_PARAMETERS,
      streamConfig,
      subject,
      initialValue: null,
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

  // Extract the actual value, using default if no ack received or no value in ack
  const actualValue = data?.value ?? defaultValue
  return {
    actualValue,
    hasReceivedMessage,
    ackData: data,
  }
}
