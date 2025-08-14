import { IconButton, Tooltip } from "@mui/material"
import type React from "react"

interface HudListButtonProps {
  tooltip: string
  icon: React.ReactNode
  onClick: () => void
  active?: boolean
}

export const HudListButton: React.FC<HudListButtonProps> = ({
  tooltip,
  icon,
  onClick,
  active = false,
}) => {
  return (
    <Tooltip title={tooltip}>
      <IconButton
        size="small"
        onClick={onClick}
        sx={{
          backgroundColor: active ? "success.main" : "transparent",
          color: active ? "success.contrastText" : "inherit",
          marginX: 0.5,
          "&:hover": {
            backgroundColor: active ? "success.dark" : "action.hover",
            color: active ? "success.contrastText" : "inherit",
          },
        }}
      >
        {icon}
      </IconButton>
    </Tooltip>
  )
}
