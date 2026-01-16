import type { Consumer, ConsumerMessages, JsMsg } from "@nats-io/jetstream"
import { useEffect, useRef } from "react"
import { isConnectionError } from "./natsErrors"

interface UseConsumeMessagesOptions {
  consumer: Consumer | null
  handleMessage: (msg: JsMsg) => Promise<void> | void
}

export const useConsumeMessages = ({
  consumer,
  handleMessage,
}: UseConsumeMessagesOptions) => {
  const handlerRef = useRef(handleMessage)

  // Update the ref when the handler changes
  useEffect(() => {
    handlerRef.current = handleMessage
  }, [handleMessage])

  // Set up the message consumption
  useEffect(() => {
    if (!consumer) return

    // Flag to handle cleanup
    let aborted = false
    // Store reference to the message iterator for cleanup
    let messagesIterator: ConsumerMessages | null = null

    // Start consuming messages
    const consumeMessages = async () => {
      try {
        messagesIterator = await consumer.consume()

        for await (const message of messagesIterator) {
          if (aborted) break

          try {
            // Use the current handler from ref
            await handlerRef.current(message)
          } catch (handlerError) {
            console.error("Error in message handler:", handlerError)
            message.term()
          }
          message.ack()
        }
      } catch (consumeError) {
        // Silently ignore connection lifecycle errors
        if (isConnectionError(consumeError)) {
          return
        }
        if (!aborted) {
          console.error("Error consuming messages:", consumeError)
        }
      }
    }

    // Start the consumer
    consumeMessages()

    // Cleanup function
    return () => {
      aborted = true
      messagesIterator?.close().catch(() => {
        // Ignore all errors during cleanup - connection may already be closed
      })
    }
  }, [consumer]) // Only re-run when consumer changes
}
