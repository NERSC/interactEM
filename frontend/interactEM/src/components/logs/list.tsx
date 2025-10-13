import { format } from "date-fns"
import { Virtuoso } from "react-virtuoso"
import type { AgentLog, OperatorLog } from "../../types/gen"
import {
  EmptyLogsMessage,
  LogInstance,
  LogLevel,
  LogMessage,
  LogModule,
  LogRow,
  LogTimestamp,
} from "./styles"

interface LogsListProps {
  logs: (AgentLog | OperatorLog)[]
  showModule?: boolean
  showInstance?: boolean
  getInstanceLabel?: (log: AgentLog | OperatorLog) => string | null
  emptyMessage?: string
}

export default function LogsList({
  logs,
  showModule = true,
  showInstance = false,
  getInstanceLabel,
  emptyMessage = "No logs yet...",
}: LogsListProps) {
  if (logs.length === 0) {
    return <EmptyLogsMessage>{emptyMessage}</EmptyLogsMessage>
  }

  return (
    <Virtuoso
      style={{ height: "100%" }}
      data={logs}
      itemContent={(_index, log) => {
        const instanceLabel =
          showInstance && getInstanceLabel ? getInstanceLabel(log) : null

        return (
          <LogRow>
            <LogTimestamp>
              {format(new Date(log.timestamp), "h:mm:ss.SSS a")}
            </LogTimestamp>
            <LogLevel level={log.level} />
            {showInstance && instanceLabel && (
              <LogInstance>{instanceLabel}</LogInstance>
            )}
            {showModule && <LogModule>{log.module}</LogModule>}
            <LogMessage>{log.log}</LogMessage>
          </LogRow>
        )
      }}
    />
  )
}
