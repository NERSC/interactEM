import {
  AckPolicy,
  DeliverPolicy,
  type JsMsg,
  ReplayPolicy,
} from "@nats-io/jetstream"
import { useCallback, useMemo, useState } from "react"
import { TABLES_STREAM } from "../constants/nats" // Ensure this constant matches the stream name used by the operator
import { useConsumeMessages } from "./useConsumeMessages"
import { useConsumer } from "./useConsumer"
import { useStream } from "./useStream"

export interface TableRow {
  [key: string]: string | number | boolean | null
}

export interface TablesDict {
  [tableName: string]: TableRow[]
}

export interface TablePayload {
  [tables: string]: TablesDict
}

const streamConfig = {
  name: TABLES_STREAM,
  subjects: [`${TABLES_STREAM}.*`],
  max_msgs_per_subject: 1,
}

export const useTableData = (operatorID: string): TablePayload | null => {
  const [tableData, setTableData] = useState<TablePayload | null>(null)

  // Ensure stream exists
  useStream(streamConfig)

  const subject = `${TABLES_STREAM}.${operatorID}`
  const consumerConfig = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.LastPerSubject,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  const consumer = useConsumer({
    stream: TABLES_STREAM,
    config: consumerConfig,
  })

  const handleMessage = useCallback(
    async (m: JsMsg) => {
      try {
        // Expect the payload to be the dictionary directly
        const jsonData = m.json<TablePayload>()

        // Basic validation: Check if it's a non-null object
        if (typeof jsonData !== "object" || jsonData === null) {
          console.error(
            `Received invalid table data structure for ${operatorID}: Expected an object, got ${typeof jsonData}.`,
          )
          m.ack()
          return
        }

        setTableData((prevData) => {
          if (JSON.stringify(jsonData) !== JSON.stringify(prevData)) {
            // Only update state if the data has actually changed
            return jsonData
          }
          return prevData
        })

        m.ack()
      } catch (error) {
        console.error(
          `Error decoding/parsing table data for ${operatorID}:`,
          error,
        )
        m.ack()
      }
    },
    [operatorID],
  )

  useConsumeMessages({
    consumer,
    handleMessage,
  })

  return tableData
}
