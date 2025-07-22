import { Handle, Position } from "@xyflow/react"
import type React from "react"

interface HandlesProps {
  inputs?: string[]
  outputs?: string[]
}

const Handles: React.FC<HandlesProps> = ({ inputs, outputs }) => (
  <>
    {inputs && inputs.length > 0 && (
      <Handle type="target" position={Position.Left} id={inputs[0]} />
    )}
    {outputs && outputs.length > 0 && (
      <Handle type="source" position={Position.Right} id={outputs[0]} />
    )}
  </>
)

export default Handles
