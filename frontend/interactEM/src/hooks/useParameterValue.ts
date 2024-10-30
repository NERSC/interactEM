import { useState, useEffect, useMemo } from "react"
import type { OperatorParameter } from "../operators"
import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { useConsumer } from "./useConsumer"
import { useNats } from "../nats/NatsContext"
import { NatsError } from "@nats-io/nats-core"
import { PARAMETERS_STREAM, PARAMETERS_UPDATE_STREAM } from "../constants/nats"

export const useParameterValue = (
  operatorID: string,
  parameter: OperatorParameter,
): string => {
  const { jc } = useNats()
  const subject = `${PARAMETERS_UPDATE_STREAM}.${operatorID}.${parameter.name}`

  const config = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.LastPerSubject,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  const consumer = useConsumer({
    stream: `${PARAMETERS_STREAM}`,
    config,
  })

  const [actualValue, setActualValue] = useState<string>(parameter.default)

  useEffect(() => {
    if (!consumer) {
      return
    }

    const consumeMessages = async () => {
      const messages = await consumer.consume()
      let operatorParamValue = parameter.default
      for await (const m of messages) {
        operatorParamValue = jc.decode(m.data) as string
        setActualValue(operatorParamValue)
        m.ack()
      }
    }

    consumeMessages()

    return () => {
      const deleteConsumer = async () => {
        try {
          const info = await consumer.info()
          if (info.stream_name) {
            await consumer.delete()
          }
        } catch (error: any) {
          if (error instanceof NatsError) {
            if (
              error.code === "404" &&
              error.message.includes("consumer not found")
            ) {
              return
            }
            console.error(`Failed to delete consumer: ${error.code}`)
          } else {
            console.error(`Failed to delete consumer: ${error.message}`)
          }
        }
      }

      deleteConsumer()
    }
  }, [consumer, jc, parameter])

  return actualValue
}
