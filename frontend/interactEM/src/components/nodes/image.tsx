import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useImage } from "../../hooks/nats/useImage"
import { useRuntimeOperatorStatusStyles } from "../../hooks/nats/useOperatorStatus"
import type { ImageNodeType } from "../../types/nodes"
import Image from "../image"
import Handles from "./handles"
import OperatorToolbar from "./toolbar"

interface ImageNodeBaseProps extends NodeProps<ImageNodeType> {
  className?: string
}

const ImageNodeBase = ({
  id,
  data,
  selected,
  className = "",
}: ImageNodeBaseProps) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const imageData = useImage(id)
  const { statusClass } = useRuntimeOperatorStatusStyles(id)

  // TODO: the data containing the positions causes a re-render of the node.

  const selectionClass = selected ? "operator-selected" : ""

  return (
    <div
      className={`operator ${className} ${statusClass} ${selectionClass}`}
      ref={nodeRef}
    >
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Image imageData={imageData} />
      <OperatorToolbar
        id={id}
        image={data.image}
        parameters={data.parameters}
        nodeRef={nodeRef}
      />
    </div>
  )
}

const ImageNode = ImageNodeBase

export default ImageNode
