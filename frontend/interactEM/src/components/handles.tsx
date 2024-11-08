import type React from "react"
import { Handle, Position } from "@xyflow/react"

interface HandlesProps {
  inputs?: string[]
  outputs?: string[]
}

const Handles: React.FC<HandlesProps> = ({ inputs, outputs }) => (
  <>
    {inputs && <Handle type="target" position={Position.Left} id={inputs[0]} />}
    {outputs && (
      <Handle type="source" position={Position.Right} id={outputs[0]} />
    )}
  </>
)

export default Handles
