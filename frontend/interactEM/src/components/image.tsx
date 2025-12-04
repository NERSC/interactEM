import { styled } from "@mui/material/styles"
import type React from "react"
import { useEffect, useState } from "react"

interface ImageProps {
  imageData: Uint8Array | null
}

interface ImgProps {
  width?: string
  height?: string
}

const Img = styled("img")<ImgProps>(({ width = "100%", height = "100%" }) => ({
  width,
  height,
  objectFit: "contain",
}))

const Image: React.FC<ImageProps> = ({ imageData }) => {
  const [imageSrc, setImageSrc] = useState<string | null>(null)

  useEffect(() => {
    if (!imageData) return

    const url = URL.createObjectURL(
      // TODO: Pass the MIME type with the image data
      new Blob([imageData], { type: "image/jpeg" }),
    )
    setImageSrc(url)

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [imageData])

  return (
    <div>{imageSrc ? <Img src={imageSrc} alt="" /> : <p>Waiting...</p>}</div>
  )
}

export default Image
