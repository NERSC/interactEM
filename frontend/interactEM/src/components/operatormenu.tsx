import type React from "react"
import type { DragEvent } from "react"
import type { Operator } from "../client/"
import { useDnD } from "../contexts/dnd"

interface OperatorMenuProps {
  operators: Operator[]
}

interface OperatorMenuItemProps {
  operator: Operator
}

export interface OperatorMenuItemDragData {
  operatorID: string
  offsetX: number
  offsetY: number
}

const OperatorMenuItem: React.FC<OperatorMenuItemProps> = ({ operator }) => {
  const [_, setValue] = useDnD<OperatorMenuItemDragData>()

  const handleOnDragStart = (event: DragEvent<HTMLDivElement>) => {
    if (setValue !== null) {
      const rect = event.currentTarget.getBoundingClientRect()
      setValue({
        operatorID: operator.id,
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

export const OperatorMenu: React.FC<OperatorMenuProps> = ({ operators }) => {
  return (
    <aside>
      <div className="description">Drag your operators into your pipeline!</div>

      {operators.map((operator: Operator) => (
        <OperatorMenuItem operator={operator} key={operator.id} />
      ))}
    </aside>
  )
}
