import type { StreamConfig, StreamInfo } from "@nats-io/jetstream"
import { useEffect, useState } from "react"
import { useNats } from "../nats/NatsContext"

export const useStream = (config: Partial<StreamConfig>): StreamInfo | null => {
  const { jetStreamClient, jetStreamManager } = useNats()
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null)

  useEffect(() => {
    const ensureStream = async () => {
      if (jetStreamManager && jetStreamClient) {
        let streamInfo: StreamInfo | null = null

        try {
          streamInfo = await jetStreamManager.streams.info(config.name)
        } catch (err: any) {
          // Check if the error is due to the stream not existing, not ideal
          // but the API doesn't current provide error codes.
          if (err.message.includes("stream not found")) {
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
