import {
  JetStreamApiCodes,
  JetStreamApiError,
  type StreamConfig,
  type StreamInfo,
} from "@nats-io/jetstream"
import type { WithRequired } from "@nats-io/nats-core/internal"
import { useEffect, useState } from "react"
import { useNats } from "../contexts/nats"

export const useStream = (
  config: WithRequired<Partial<StreamConfig>, "name">,
): StreamInfo | null => {
  const { jetStreamClient, jetStreamManager } = useNats()
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null)

  useEffect(() => {
    const ensureStream = async () => {
      if (jetStreamManager && jetStreamClient) {
        let streamInfo: StreamInfo | null = null

        try {
          streamInfo = await jetStreamManager.streams.info(config.name)
        } catch (err: any) {
          if (
            err instanceof JetStreamApiError &&
            err.code === JetStreamApiCodes.StreamNotFound
          ) {
            streamInfo = await jetStreamManager.streams.add(config)
          } else {
            throw err
          }
        }

        setStreamInfo(streamInfo)
      }
    }

    ensureStream()
  }, [jetStreamManager, jetStreamClient, config])

  return streamInfo
}
