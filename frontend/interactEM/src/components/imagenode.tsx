import type { Node, NodeProps } from "@xyflow/react"
import { useRef } from "react"

import { useImage } from "../hooks/useImage"
import type { OperatorParameter } from "../operators"
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

  return (
    // TODO Should probably update the class
    <div className="operator" ref={nodeRef}>
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Image imageData={imageData} />
    </div>
  )
}

export default ImageNode
