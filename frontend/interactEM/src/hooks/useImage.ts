import { useMemo, useState, useCallback } from "react"
import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { IMAGES_STREAM } from "../constants/nats"
import { useConsumer } from "./useConsumer"
import { useConsumeMessages } from "./useConsumeMessages"
import type { JsMsg } from "@nats-io/jetstream"
import { useStream } from "./useStream"

const streamConfig = {
  name: IMAGES_STREAM,
  subjects: [`${IMAGES_STREAM}.>`],
  max_msgs_per_subject: 1,
}

export const useImage = (operatorID: string): Uint8Array | null => {
  const subject = `${IMAGES_STREAM}.${operatorID}`

  const consumerConfig = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.LastPerSubject,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  // ensure stream
  // TODO: there is still for some reason a bug here that requires us to run things twice.
  // hook.js:608 Failed to create ephemeral consumer in stream "images": StreamNotFoundError: stream not found
  //   at ConsumerAPIImpl.parseJsResponse (chunk-64MGA3Q7.js?v=f913c564:408:21)
  //   at ConsumerAPIImpl._request (chunk-64MGA3Q7.js?v=f913c564:375:25)
  //   at async ConsumerAPIImpl.add (chunk-64MGA3Q7.js?v=f913c564:736:19)
  //   at async createConsumer (useConsumer.ts:58:11)
  useStream(streamConfig)

  const consumer = useConsumer({
    stream: IMAGES_STREAM,
    config: consumerConfig,
  })

  const [imageData, setImageData] = useState<Uint8Array | null>(null)

  const handleMessage = useCallback(async (m: JsMsg) => {
    setImageData(m.data)
  }, [])

  useConsumeMessages({ consumer, handleMessage })

  return imageData
}
