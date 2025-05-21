import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useImage } from "../../hooks/nats/useImage"
import type { ImageNodeType } from "../../types/nodes"
import Image from "../image"
import Handles from "./handles"
import { withOperatorStatus } from "./statuscontrol"

interface ImageNodeBaseProps extends NodeProps<ImageNodeType> {
  className?: string
}

const ImageNodeBase = ({ id, data, className = "" }: ImageNodeBaseProps) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const imageData = useImage(id)

  // TODO: the data containing the positions causes a re-render of the node.

  return (
    // TODO Should probably update the class
    <div className={`operator ${className}`} ref={nodeRef}>
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Image imageData={imageData} />
    </div>
  )
}

const ImageNode = withOperatorStatus(ImageNodeBase)

export default ImageNode
