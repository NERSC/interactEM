import { STREAM_IMAGES } from "../../constants/nats"
import { useOperatorInSelectedPipeline } from "./useOperatorStatus"
import { useStreamMessage } from "./useStreamMessage"

export const useImage = (operatorID: string): Uint8Array | null => {
  const subject = `${STREAM_IMAGES}.${operatorID}`
  const { isInRunningPipeline } = useOperatorInSelectedPipeline(operatorID)

  const { data } = useStreamMessage<Uint8Array>({
    streamName: STREAM_IMAGES,
    subject,
    enabled: isInRunningPipeline,
    transform: (_, originalMessage) => {
      // Return the raw binary data instead of parsing as JSON
      return originalMessage.data
    },
  })

  return isInRunningPipeline ? data : null
}
