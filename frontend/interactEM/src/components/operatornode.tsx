import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import type { OperatorNodeType } from "../types/nodes"
import Handles from "./handles"
import OperatorHeader from "./operatorheader"
import OperatorToolbar from "./operatortoolbar"

const OperatorNode = ({ id, data }: NodeProps<OperatorNodeType>) => {
  const nodeRef = useRef<HTMLDivElement>(null)

  return (
    <div className="operator" ref={nodeRef}>
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

export default OperatorNode
