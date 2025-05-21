import { DeliverPolicy } from "@nats-io/jetstream"
import { OPERATORS_STREAM } from "../../constants/nats"
import type { OperatorEvent } from "../../types/events"
import { useStreamMessage } from "./useStreamMessage"

const streamConfig = {
  name: OPERATORS_STREAM,
  subjects: [`${OPERATORS_STREAM}.>`],
}

export const useOperatorEvents = (operatorID: string) => {
  const subject = `${OPERATORS_STREAM}.${operatorID}.events`

  const { data: operatorEvent } = useStreamMessage<OperatorEvent>({
    streamName: OPERATORS_STREAM,
    streamConfig,
    subject,
    deliverPolicy: DeliverPolicy.Last,
    transform: (jsonData) => {
      try {
        // Basic validation could be added here if needed
        return jsonData as OperatorEvent
      } catch (e) {
        console.error("Failed to parse operator event data", e)
        return null
      }
    },
  })

  return { operatorEvent }
}
