import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useImage } from "../../hooks/nats/useImage"
import { useRuntimeOperatorStatusStyles } from "../../hooks/nats/useOperatorStatus"
import type { ImageNodeType } from "../../types/nodes"
import Image from "../image"
import Handles from "./handles"

interface ImageNodeBaseProps extends NodeProps<ImageNodeType> {
  className?: string
}

const ImageNodeBase = ({ id, data, className = "" }: ImageNodeBaseProps) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const imageData = useImage(id)
  const { statusClass } = useRuntimeOperatorStatusStyles(id)

  // TODO: the data containing the positions causes a re-render of the node.

  return (
    <div className={`operator ${className} ${statusClass}`} ref={nodeRef}>
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Image imageData={imageData} />
    </div>
  )
}

const ImageNode = ImageNodeBase

export default ImageNode
