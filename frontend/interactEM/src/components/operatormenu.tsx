import type React from "react"
import type { DragEvent } from "react"
import type { OperatorSpec } from "../client/"
import { useDnD } from "../contexts/dnd"
import useOperatorSpecs from "../hooks/api/useOperatorSpecs"

interface OperatorMenuItemProps {
  operator: OperatorSpec
}

export interface OperatorMenuItemDragData {
  specID: string
  offsetX: number
  offsetY: number
}

const OperatorMenuItem: React.FC<OperatorMenuItemProps> = ({ operator }) => {
  const [_, setValue] = useDnD<OperatorMenuItemDragData>()

  const handleOnDragStart = (event: DragEvent<HTMLDivElement>) => {
    if (setValue !== null) {
      const rect = event.currentTarget.getBoundingClientRect()
      setValue({
        specID: operator.id,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
      })
    }
    event.dataTransfer.effectAllowed = "move"
  }

  return (
    <div
      className="operator-menu-item"
      onDragStart={(event) => handleOnDragStart(event)}
      key={operator.id}
      draggable
    >
      {operator.label}
    </div>
  )
}

export const OperatorMenu: React.FC = () => {
  const { operatorSpecs, isLoading, isRefreshing, refetch } = useOperatorSpecs()
  return (
    <aside>
      <div className="operator-menu-controls">
        <button
          type="button"
          onClick={refetch}
          disabled={isRefreshing || isLoading}
          className="refresh-button"
        >
          {isRefreshing ? "Refreshing..." : "Refresh Operators"}
        </button>
      </div>

      {operatorSpecs?.map((operator: OperatorSpec) => (
        <OperatorMenuItem operator={operator} key={operator.id} />
      ))}
    </aside>
  )
}
