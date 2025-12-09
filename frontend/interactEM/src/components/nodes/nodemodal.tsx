import { Box, Modal } from "@mui/material"
import type React from "react"
import { useCallback, useState } from "react"

type UseNodeAnchoredModalArgs = {
  nodeRef: React.RefObject<HTMLDivElement>
  offsetY?: number
}

type AnchoredOperatorModalProps = {
  open: boolean
  onClose: () => void
  modalStyle: React.CSSProperties
  children: React.ReactNode
}

export const useNodeAnchoredModal = ({
  nodeRef,
  offsetY = 10,
}: UseNodeAnchoredModalArgs) => {
  const [open, setOpen] = useState(false)
  const [modalStyle, setModalStyle] = useState<React.CSSProperties>({})

  const handleOpen = useCallback(
    (event?: React.MouseEvent<HTMLElement>) => {
      event?.stopPropagation()

      if (nodeRef.current) {
        const rect = nodeRef.current.getBoundingClientRect()
        setModalStyle({
          position: "absolute",
          top: rect.bottom + window.scrollY + offsetY,
          left: rect.left + window.scrollX + rect.width / 2,
          transform: "translateX(-50%)",
        })
      }

      setOpen(true)
    },
    [nodeRef, offsetY],
  )

  const handleClose = useCallback(() => setOpen(false), [])

  return { open, modalStyle, handleOpen, handleClose }
}

export const AnchoredOperatorModal: React.FC<AnchoredOperatorModalProps> = ({
  open,
  onClose,
  modalStyle,
  children,
}) => (
  <Modal open={open} onClose={onClose} sx={{ position: "absolute" }}>
    <Box
      className="operator-modal-box"
      style={modalStyle}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="operator-modal-content">{children}</div>
    </Box>
  </Modal>
)
