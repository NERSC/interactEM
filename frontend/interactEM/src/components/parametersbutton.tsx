// ParametersButton.tsx
import type React from "react"
import { useState } from "react"
import { IconButton, Popover } from "@mui/material"
import SettingsIcon from "@mui/icons-material/Settings"
import ParameterUpdater from "./parameterupdater"
import type { OperatorParameter } from "../operators"

interface ParametersButtonProps {
  operatorID: string
  parameters: OperatorParameter[]
  nodeRef: React.RefObject<HTMLDivElement>
}

const ParametersButton: React.FC<ParametersButtonProps> = ({
  operatorID,
  parameters,
  nodeRef,
}) => {
  const [anchorPosition, setAnchorPosition] = useState<{
    top: number
    left: number
  } | null>(null)

  const handleOpenPopover = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation() // Prevent node drag when clicking the button

    if (nodeRef.current) {
      // Use getBoundingClientRect to get the position of the node
      // and set the popover position
      const rect = nodeRef.current.getBoundingClientRect()
      setAnchorPosition({
        top: rect.bottom + window.scrollY,
        left: rect.left + rect.width / 2 + window.scrollX,
      })
    }
  }

  const handleClosePopover = () => {
    setAnchorPosition(null)
  }

  const open = Boolean(anchorPosition)

  return (
    <>
      <IconButton onClick={handleOpenPopover} size="small">
        <SettingsIcon fontSize="small" />
        <span className="operator-button-text">Parameters</span>
      </IconButton>

      <Popover
        open={open}
        onClose={handleClosePopover}
        anchorReference="anchorPosition"
        anchorPosition={anchorPosition || { top: 0, left: 0 }}
        transformOrigin={{
          vertical: "top",
          horizontal: "center",
        }}
      >
        <div className="operator-popover-content">
          {parameters.map((param) => (
            <div key={param.name} className="parameter-item">
              <ParameterUpdater parameter={param} operatorID={operatorID} />
            </div>
          ))}
        </div>
      </Popover>
    </>
  )
}

export default ParametersButton
