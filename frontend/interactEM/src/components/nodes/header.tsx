import ErrorIcon from "@mui/icons-material/Error"
import { Tooltip } from "@mui/material"
import type React from "react"
import { useOperatorEvents } from "../../hooks/useOperatorEvents"
import { type OperatorErrorEvent, OperatorEventType } from "../../types/events"

interface OperatorHeaderProps {
  id: string
  label: string
}

const OperatorHeader: React.FC<OperatorHeaderProps> = ({ id, label }) => {
  const { operatorEvent } = useOperatorEvents(id)

  return (
    <div className="operator-header">
      {label}
      {operatorEvent?.type === OperatorEventType.ERROR && (
        <Tooltip
          title={(operatorEvent as OperatorErrorEvent).message || "Error"}
          placement="top"
        >
          <ErrorIcon className="operator-error-icon" />
        </Tooltip>
      )}
    </div>
  )
}

export default OperatorHeader
