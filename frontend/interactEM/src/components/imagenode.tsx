import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useImage } from "../hooks/useImage"
import type { ImageNodeType } from "../types/nodes"
import Handles from "./handles"
import Image from "./image"

const ImageNode = ({ id, data }: NodeProps<ImageNodeType>) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const imageData = useImage(id)

  // TODO: the data containing the positions causes a re-render of the node.

  return (
    // TODO Should probably update the class
    <div className="operator" ref={nodeRef}>
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Image imageData={imageData} />
    </div>
  )
}

export default ImageNode
