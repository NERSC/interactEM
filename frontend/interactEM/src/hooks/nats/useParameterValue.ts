import {
  PARAMETERS_STREAM,
  PARAMETERS_UPDATE_STREAM,
} from "../../constants/nats"
import { useStreamMessage } from "./useStreamMessage"

const streamConfig = {
  name: PARAMETERS_STREAM,
  subjects: [`${PARAMETERS_STREAM}.>`],
}

export const useParameterValue = (
  operatorID: string,
  name: string,
  defaultValue: string,
): { actualValue: string; hasReceivedMessage: boolean } => {
  const subject = `${PARAMETERS_UPDATE_STREAM}.${operatorID}.${name}`

  const { data, hasReceivedMessage } = useStreamMessage<string>({
    streamName: PARAMETERS_STREAM,
    streamConfig,
    subject,
    initialValue: defaultValue,
    transform: (jsonData) => {
      // Simple validation could be added here if needed
      return jsonData as string
    },
  })

  return { actualValue: data ?? defaultValue, hasReceivedMessage }
}
