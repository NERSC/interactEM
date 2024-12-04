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
