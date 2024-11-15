import type React from "react"
import ErrorIcon from "@mui/icons-material/Error"
import { useOperatorEvents } from "../hooks/useOperatorEvents"
import { Tooltip } from "@mui/material"

interface OperatorHeaderProps {
  id: string
  label: string
}

const OperatorHeader: React.FC<OperatorHeaderProps> = ({ id, label }) => {
  const { operatorErrorEvent, isError } = useOperatorEvents(id)
  return (
    <div className="operator-header">
      {label}
      {isError && operatorErrorEvent && (
        <Tooltip title={operatorErrorEvent.message || "Error"} placement="top">
          <ErrorIcon className="operator-error-icon" />
        </Tooltip>
      )}
    </div>
  )
}

export default OperatorHeader
