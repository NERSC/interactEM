import { STREAM_TABLES } from "../../constants/nats"
import { useStreamMessage } from "./useStreamMessage"

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
  name: STREAM_TABLES,
  subjects: [`${STREAM_TABLES}.*`],
  max_msgs_per_subject: 1,
}

export const useTableData = (operatorID: string): TablePayload | null => {
  const subject = `${STREAM_TABLES}.${operatorID}`

  const { data } = useStreamMessage<TablePayload>({
    streamName: STREAM_TABLES,
    streamConfig,
    subject,
    transform: (jsonData) => {
      // Basic validation: Check if it's a non-null object
      if (typeof jsonData !== "object" || jsonData === null) {
        console.error(
          `Received invalid table data structure for ${operatorID}: Expected an object, got ${typeof jsonData}.`,
        )
        return null
      }
      return jsonData as TablePayload
    },
  })

  return data
}
