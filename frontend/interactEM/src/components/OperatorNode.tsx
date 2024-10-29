import type { Node, NodeProps } from "@xyflow/react"
import OperatorHeader from "./OperatorHeader"
import ParametersButton from "./ParametersButton"
import OperatorHandles from "./OperatorHandles"
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
      <OperatorHeader id={id} label={data.label} image={data.image} />

      {data.parameters && (
        <ParametersButton
          operatorID={id}
          parameters={data.parameters}
          nodeRef={nodeRef}
        />
      )}
      <OperatorHandles inputs={data.inputs} outputs={data.outputs} />
    </div>
  )
}

export default OperatorNode
