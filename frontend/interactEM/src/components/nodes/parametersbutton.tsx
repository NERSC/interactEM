// ParametersButton.tsx

import SettingsIcon from "@mui/icons-material/Settings"
import { Box, IconButton, Modal } from "@mui/material"
import type React from "react"
import { useState } from "react"
import type { OperatorParameter } from "../../client"
import ParameterUpdater from "./parameterupdater"

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
  const [open, setOpen] = useState(false)
  const [modalStyle, setModalStyle] = useState<React.CSSProperties>({})

  const handleOpenModal = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation()

    if (nodeRef.current) {
      // Get the position of the node
      const rect = nodeRef.current.getBoundingClientRect()
      setModalStyle({
        position: "absolute",
        top: rect.bottom + window.scrollY + 10,
        left: rect.left + window.scrollX + rect.width / 2,
        transform: "translateX(-50%)",
      })
    }

    setOpen(true)
  }

  const handleCloseModal = () => {
    setOpen(false)
  }

  return (
    <>
      <IconButton
        onClick={handleOpenModal}
        size="small"
        className="nodrag"
        aria-label="Parameters"
      >
        <SettingsIcon fontSize="small" />
      </IconButton>
      <Modal
        open={open}
        onClose={handleCloseModal}
        sx={{ position: "absolute" }}
      >
        <Box
          className="operator-modal-box"
          style={modalStyle}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="operator-modal-content">
            {parameters.map((param) => (
              <div key={param.name} className="parameter-item">
                <ParameterUpdater parameter={param} operatorID={operatorID} />
              </div>
            ))}
          </div>
        </Box>
      </Modal>
    </>
  )
}

export default ParametersButton
