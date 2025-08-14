import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useRuntimeOperatorStatusStyles } from "../../hooks/nats/useOperatorStatus"
import { ViewMode, useViewModeStore } from "../../stores"
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

  return (
    <div className={`operator ${className} ${statusClass}`} ref={nodeRef}>
      <OperatorHeader id={id} label={data.label} />
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <OperatorToolbar
        id={id}
        image={data.image}
        parameters={data.parameters}
        nodeRef={nodeRef}
      />
    </div>
  )
}

const OperatorNode = OperatorNodeBase

export default OperatorNode
