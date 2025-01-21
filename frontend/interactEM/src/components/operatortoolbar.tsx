import InfoIcon from "@mui/icons-material/Info"
import { IconButton, Tooltip } from "@mui/material"
import type React from "react"
import type { OperatorParameter } from "../operators"
import ParametersButton from "./parametersbutton"

interface OperatorToolbarProps {
  id: string
  image: string
  parameters?: OperatorParameter[]
  nodeRef: React.RefObject<HTMLDivElement>
}

const OperatorToolbar: React.FC<OperatorToolbarProps> = ({
  id,
  image,
  parameters,
  nodeRef,
}) => {
  return (
    <div className="operator-toolbar">
      <div className="operator-icons">
        {parameters && (
          <ParametersButton
            operatorID={id}
            parameters={parameters}
            nodeRef={nodeRef}
          />
        )}

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
    </div>
  )
}

export default OperatorToolbar
