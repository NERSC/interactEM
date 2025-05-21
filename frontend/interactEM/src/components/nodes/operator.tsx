import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import type { OperatorNodeType } from "../../types/nodes"
import Handles from "./handles"
import OperatorHeader from "./header"
import { withOperatorStatus } from "./statuscontrol"
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

  return (
    <div className={`operator ${className}`} ref={nodeRef}>
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

const OperatorNode = withOperatorStatus(OperatorNodeBase)

export default OperatorNode
