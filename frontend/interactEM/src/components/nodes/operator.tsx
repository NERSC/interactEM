import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useRuntimeOperatorStatusStyles } from "../../hooks/nats/useOperatorStatus"
import { useViewModeStore, ViewMode } from "../../stores"
import type { OperatorNodeType } from "../../types/nodes"
import Handles from "./handles"
import OperatorHeader from "./header"
import OperatorToolbar from "./toolbar"

interface OperatorNodeBaseProps extends NodeProps<OperatorNodeType> {
  className?: string
}

const OperatorNodeBase = ({
  id,
  data,
  selected,
  className = "",
}: OperatorNodeBaseProps) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const { viewMode } = useViewModeStore()
  let statusClass = ""
  if (viewMode === ViewMode.Runtime) {
    const { statusClass: runtimeStatusClass } =
      useRuntimeOperatorStatusStyles(id)
    statusClass = runtimeStatusClass
  }

  const selectionClass = selected ? "operator-selected" : ""

  return (
    <div
      className={`operator ${className} ${statusClass} ${selectionClass}`}
      ref={nodeRef}
    >
      <OperatorHeader id={id} label={data.label} />
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <OperatorToolbar
        id={id}
        image={data.image}
        parameters={data.parameters}
        triggers={data.triggers}
        nodeRef={nodeRef}
      />
    </div>
  )
}

const OperatorNode = OperatorNodeBase

export default OperatorNode
