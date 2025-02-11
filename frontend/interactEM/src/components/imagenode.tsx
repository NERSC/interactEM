import type { Node, NodeProps } from "@xyflow/react"
import { useRef } from "react"

import type { OperatorParameter } from "../client"
import { useImage } from "../hooks/useImage"
import Handles from "./handles"
import Image from "./image"

export type ImageNode = Node<
  {
    label: string
    image: string
    inputs?: string[]
    outputs?: string[]
    parameters?: OperatorParameter[]
  },
  "image"
>

const ImageNode = ({ id, data }: NodeProps<ImageNode>) => {
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
