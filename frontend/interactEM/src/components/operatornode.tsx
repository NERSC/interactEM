import { Handle, type Node, type NodeProps, Position } from "@xyflow/react"

type OperatorNode = Node<
  { label: string; image: string; inputs?: string[]; outputs?: string[] },
  "operator"
>

const OperatorNode = ({ data }: NodeProps<OperatorNode>) => {
  return (
    <div className="react-flow__node-default">
      {data.label && <div>{data.label}</div>}
      {data.inputs && (
        <Handle type="target" position={Position.Left} id={data.inputs[0]} />
      )}
      {data.outputs && (
        <Handle type="source" position={Position.Right} id={data.outputs[0]} />
      )}
    </div>
  )
}

export default OperatorNode
