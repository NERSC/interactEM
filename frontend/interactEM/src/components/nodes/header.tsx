import type React from "react"

interface OperatorHeaderProps {
  id: string
  label: string
}

const OperatorHeader: React.FC<OperatorHeaderProps> = ({ label }) => {
  // TODO: reimplement error handling - from OperatorVal (status bucket)
  return (
    <div className="operator-header">
      {label}
      {/* {operatorEvent?.type === OperatorEventType.error && (
        <Tooltip
          title={(operatorEvent as OperatorErrorEvent).message || "Error"}
          placement="top"
        >
          <ErrorIcon className="operator-error-icon" />
        </Tooltip>
      )} */}
    </div>
  )
}

export default OperatorHeader
