import type React from "react"
import { useOperatorStatus } from "../../hooks/nats/useOperatorStatus"

export const withOperatorStatus = <P extends { id: string }>(
  Component: React.ComponentType<P>,
): React.FC<P> => {
  return (props: P) => {
    const { status } = useOperatorStatus(props.id)

    // Only apply status class if we have a status (which means the operator is part of a running pipeline)
    let statusClass = ""

    if (status === "initializing") {
      statusClass = "operator-status-initializing"
    } else if (status === "running") {
      statusClass = "operator-status-running"
    } else if (status === "shutting_down") {
      statusClass = "operator-status-shutting-down"
    } else {
      statusClass = "operator-status-offline"
    }

    // Only pass the statusClass if we have a status
    const className = status ? statusClass : ""

    // Pass the statusClass as a prop to be used by the component
    return <Component {...props} className={className} />
  }
}
