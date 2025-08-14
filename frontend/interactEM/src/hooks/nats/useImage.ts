import { STREAM_IMAGES } from "../../constants/nats"
import { useStreamMessage } from "./useStreamMessage"

const streamConfig = {
  name: STREAM_IMAGES,
  subjects: [`${STREAM_IMAGES}.>`],
  max_msgs_per_subject: 1,
}

export const useImage = (operatorID: string): Uint8Array | null => {
  const subject = `${STREAM_IMAGES}.${operatorID}`

  // ensure stream
  // TODO: there is still for some reason a bug here that requires us to run things twice.
  // hook.js:608 Failed to create ephemeral consumer in stream "images": StreamNotFoundError: stream not found
  //   at ConsumerAPIImpl.parseJsResponse (chunk-64MGA3Q7.js?v=f913c564:408:21)
  //   at ConsumerAPIImpl._request (chunk-64MGA3Q7.js?v=f913c564:375:25)
  //   at async ConsumerAPIImpl.add (chunk-64MGA3Q7.js?v=f913c564:736:19)
  //   at async createConsumer (useConsumer.ts:58:11)
  // Note: Special transform function for binary data
  const { data } = useStreamMessage<Uint8Array>({
    streamName: STREAM_IMAGES,
    streamConfig,
    subject,
    transform: (_, originalMessage) => {
      // Return the raw binary data instead of parsing as JSON
      return originalMessage.data
    },
  })

  return data
}
