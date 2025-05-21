import type { Consumer, JsMsg } from "@nats-io/jetstream"
import { useEffect, useRef } from "react"

interface UseConsumeMessagesOptions {
  consumer: Consumer | null
  handleMessage: (msg: JsMsg) => Promise<void> | void
}

export const useConsumeMessages = ({
  consumer,
  handleMessage,
}: UseConsumeMessagesOptions) => {
  const handlerRef = useRef(handleMessage)

  // We should be able to pass in memoized or non-memoized
  // functions and it should be fine...

  // I pass in callbacks be safe

  // TODO: still getting this error, thought i fixed it:

  // Error consuming messages: InvalidOperationError: ordered consumer doesn't support concurrent consume
  //   at PullConsumerImpl.consume (chunk-64MGA3Q7.js?v=f913c564:1502:35)
  //   at consumeMessages (useConsumeMessages.ts:36:41)
  //   at useConsumeMessages.ts:47:5
  //   at commitHookEffectListMount (chunk-XQLYTHWV.js?v=f913c564:16915:34)
  //   at commitPassiveMountOnFiber (chunk-XQLYTHWV.js?v=f913c564:18156:19)
  //   at commitPassiveMountEffects_complete (chunk-XQLYTHWV.js?v=f913c564:18129:17)
  //   at commitPassiveMountEffects_begin (chunk-XQLYTHWV.js?v=f913c564:18119:15)
  //   at commitPassiveMountEffects (chunk-XQLYTHWV.js?v=f913c564:18109:11)
  //   at flushPassiveEffectsImpl (chunk-XQLYTHWV.js?v=f913c564:19490:11)
  //   at flushPassiveEffects (chunk-XQLYTHWV.js?v=f913c564:19447:22)

  // Update the ref when the handler changes
  useEffect(() => {
    handlerRef.current = handleMessage
  }, [handleMessage])

  // Set up the message consumption
  useEffect(() => {
    if (!consumer) return

    // Flag to handle cleanup
    let aborted = false

    // Start consuming messages
    const consumeMessages = async () => {
      try {
        const messages = await consumer.consume()

        for await (const message of messages) {
          if (aborted) break

          try {
            // Use the current handler from ref
            await handlerRef.current(message)
          } catch (handlerError) {
            console.error("Error in message handler:", handlerError)
          } finally {
            // Always ack the message to prevent getting stuck
            message.ack()
          }
        }
      } catch (consumeError) {
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
    }
  }, [consumer]) // Only re-run when consumer changes
}
