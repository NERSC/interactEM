import type { Node, NodeProps } from "@xyflow/react"
import OperatorHeader from "./operatorheader"
import Handles from "./handles"
import OperatorToolbar from "./operatortoolbar"
import type { OperatorParameter } from "../operators"
import { useRef } from "react"

export type OperatorNode = Node<
  {
    label: string
    image: string
    inputs?: string[]
    outputs?: string[]
    parameters?: OperatorParameter[]
  },
  "operator"
>

const OperatorNode = ({ id, data }: NodeProps<OperatorNode>) => {
  const nodeRef = useRef<HTMLDivElement>(null)

  return (
    <div className="operator" ref={nodeRef}>
      <OperatorHeader label={data.label} />
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
