import type { Consumer, ConsumerConfig } from "@nats-io/jetstream"
import { JetStreamError } from "@nats-io/jetstream"
import { useEffect, useRef, useState } from "react"
import { useNats } from "../../contexts/nats"
import { isConnectionError } from "./natsErrors"

interface UseConsumerOptions {
  stream: string
  config: ConsumerConfig | null
}

export const useConsumer = ({
  stream,
  config,
}: UseConsumerOptions): Consumer | null => {
  const { jetStreamClient, jetStreamManager, isConnected } = useNats()
  const [consumer, setConsumer] = useState<Consumer | null>(null)
  const isMountedRef = useRef(true)
  const consumerRef = useRef<Consumer | null>(null)

  useEffect(() => {
    // Mark component as mounted when effect runs
    isMountedRef.current = true
    // Create abort signal for this effect instance to handle race conditions
    // when connection drops mid-create and reconnects before promise settles
    const abortController = new AbortController()

    // If config is null, clear the consumer
    if (!config) {
      const consumerToDelete = consumerRef.current
      if (consumerToDelete) {
        consumerToDelete.delete().catch((error) => {
          if (!isConnectionError(error)) {
            console.error("Error deleting consumer:", error)
          }
        })
        consumerRef.current = null
      }
      setConsumer(null)
      return
    }

    const deleteConsumer = async (consumerToDelete: Consumer | null) => {
      if (!consumerToDelete) return
      try {
        await consumerToDelete.delete()
        // If the deleted consumer is the one we created, clear the ref
        if (consumerRef.current === consumerToDelete) {
          consumerRef.current = null
        }
      } catch (error) {
        if (isConnectionError(error)) {
          // dont delete if we dont have a connection
          return
        }
        if (error instanceof JetStreamError) {
          console.error(
            `JetStream error during consumer deletion: ${error.message}`,
          )
        } else {
          console.error(`Failed to delete consumer: ${error}`)
        }
      }
    }

    const createConsumer = async () => {
      if (!jetStreamManager || !jetStreamClient || !isConnected) {
        return
      }

      try {
        const consumerInfo = await jetStreamManager.consumers.add(
          stream,
          config,
        )
        const newConsumer = await jetStreamClient.consumers.get(
          stream,
          consumerInfo.name,
        )

        // Check if this effect instance was aborted before setting state
        if (abortController.signal.aborted) {
          await deleteConsumer(newConsumer)
          return
        }

        if (isMountedRef.current) {
          setConsumer(newConsumer)
          consumerRef.current = newConsumer
        } else {
          // If unmounted before consumer was set, delete it
          await deleteConsumer(newConsumer)
        }
      } catch (error) {
        // Check if this effect instance was aborted before handling error
        if (abortController.signal.aborted) {
          return
        }

        if (isConnectionError(error)) {
          return
        }
        console.error(`Failed to create consumer in stream "${stream}":`, error)
      }
    }

    createConsumer()

    return () => {
      isMountedRef.current = false
      abortController.abort()
      const consumerToDelete = consumerRef.current

      if (consumerToDelete) {
        deleteConsumer(consumerToDelete).catch((error) => {
          if (!isConnectionError(error)) {
            console.error("Error deleting consumer during cleanup:", error)
          }
        })
      }
    }
  }, [jetStreamManager, jetStreamClient, stream, config, isConnected])

  return consumer
}
