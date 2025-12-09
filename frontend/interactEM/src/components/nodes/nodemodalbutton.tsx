import { Box, IconButton, Stack, Tooltip, Typography } from "@mui/material"
import type React from "react"
import { AnchoredOperatorModal, useNodeAnchoredModal } from "./nodemodal"

interface NodeModalButtonProps {
  nodeRef: React.RefObject<HTMLDivElement>
  icon: React.ReactNode
  label: string
  title: string | null
  disabled?: boolean
  children: React.ReactNode
  minWidth?: number
}

const NodeModalButton: React.FC<NodeModalButtonProps> = ({
  nodeRef,
  icon,
  label,
  title,
  disabled = false,
  children,
  minWidth = 300,
}) => {
  const { open, modalStyle, handleOpen, handleClose } = useNodeAnchoredModal({
    nodeRef,
  })

  return (
    <>
      <Tooltip title={disabled ? `${label} (Disabled)` : label} placement="top">
        <Box component="span" sx={{ display: "inline-flex" }}>
          <IconButton
            onClick={handleOpen}
            size="small"
            className="nodrag"
            aria-label={label}
            disabled={disabled}
          >
            {icon}
          </IconButton>
        </Box>
      </Tooltip>

      <AnchoredOperatorModal
        open={open}
        onClose={handleClose}
        modalStyle={modalStyle}
      >
        <Stack spacing={2} sx={{ minWidth, width: "100%", p: 0.5 }}>
          {title && (
            <Typography variant="overline" color="text.secondary">
              {title}
            </Typography>
          )}
          {children}
        </Stack>
      </AnchoredOperatorModal>
    </>
  )
}

export default NodeModalButton
