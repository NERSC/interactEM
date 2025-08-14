import { Edit, PlayArrow } from "@mui/icons-material"
import { IconButton, Tooltip } from "@mui/material"
import type React from "react"
import { ViewMode, useViewModeStore } from "../../stores"

export const ViewModeToggle: React.FC = () => {
  const { viewMode, setViewMode } = useViewModeStore()

  const handleToggle = () => {
    const newMode =
      viewMode === ViewMode.Composer ? ViewMode.Runtime : ViewMode.Composer
    setViewMode(newMode)
  }

  const isComposer = viewMode === ViewMode.Composer

  return (
    <Tooltip
      title={isComposer ? "Switch to Runtime View" : "Switch to Composer View"}
    >
      <IconButton
        size="small"
        onClick={handleToggle}
        sx={{
          backgroundColor: "transparent",
          color: "inherit",
          marginX: 0.5,
          "&:hover": {
            backgroundColor: "action.hover",
          },
        }}
      >
        {isComposer ? (
          <PlayArrow fontSize="small" />
        ) : (
          <Edit fontSize="small" />
        )}
      </IconButton>
    </Tooltip>
  )
}
