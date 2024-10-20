import type React from "react"
import { IconButton, Tooltip } from "@mui/material"
import InfoIcon from "@mui/icons-material/Info"

interface OperatorHeaderProps {
  id: string
  label: string
  image: string
}

const OperatorHeader: React.FC<OperatorHeaderProps> = ({
  id,
  label,
  image,
}) => {
  return (
    <div className="operator-header">
      <div className="operator-label">{label}</div>
      <Tooltip
        title={
          <div>
            <div>ID: {id}</div>
            <div>Image: {image}</div>
          </div>
        }
        placement="top"
      >
        <IconButton size="small" aria-label="Info">
          <InfoIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </div>
  )
}

export default OperatorHeader
