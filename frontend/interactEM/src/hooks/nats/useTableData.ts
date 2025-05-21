import { TABLES_STREAM } from "../../constants/nats"
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
  name: TABLES_STREAM,
  subjects: [`${TABLES_STREAM}.*`],
  max_msgs_per_subject: 1,
}

export const useTableData = (operatorID: string): TablePayload | null => {
  const subject = `${TABLES_STREAM}.${operatorID}`

  const { data } = useStreamMessage<TablePayload>({
    streamName: TABLES_STREAM,
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
