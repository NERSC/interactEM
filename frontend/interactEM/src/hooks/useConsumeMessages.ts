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
  // store a ref to the handleMessage function
  // instead of including it in the dependency array
  // This way we dont have to worry about re-rendering
  // and getting errors about consumer doing concurrent
  // consumes.

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

  const handleMessageRef = useRef(handleMessage)
  useEffect(() => {
    handleMessageRef.current = handleMessage
  }, [handleMessage])

  useEffect(() => {
    if (!consumer) return

    let isCancelled = false

    const consumeMessages = async () => {
      try {
        const messages = await consumer.consume()
        for await (const m of messages) {
          if (isCancelled) break
          await handleMessageRef.current(m)
          m.ack()
        }
      } catch (error) {
        console.error("Error consuming messages:", error)
      }
    }

    consumeMessages()

    return () => {
      isCancelled = true
    }
  }, [consumer])
}
