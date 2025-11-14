import CancelIcon from "@mui/icons-material/Cancel"
import SaveIcon from "@mui/icons-material/Save"
import { Box, IconButton, TextField, Tooltip } from "@mui/material"
import type React from "react"

interface InlineEditFieldProps {
  isEditing: boolean
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onKeyDown: (e: React.KeyboardEvent) => void
  onSaveClick: (e: React.MouseEvent) => void
  onCancelClick: (e: React.MouseEvent) => void
  isLoading?: boolean
  children: React.ReactNode
}

export const InlineEditField: React.FC<InlineEditFieldProps> = ({
  isEditing,
  value,
  onChange,
  onKeyDown,
  onSaveClick,
  onCancelClick,
  isLoading = false,
  children,
}) => {
  if (isEditing) {
    return (
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          width: "100%",
          px: 2,
          py: 1,
        }}
      >
        <TextField
          value={value}
          onChange={onChange}
          onKeyDown={onKeyDown}
          variant="standard"
          size="small"
          fullWidth
          autoFocus
          onClick={(e) => e.stopPropagation()}
          disabled={isLoading}
        />
        <Box sx={{ display: "flex", ml: 1, flexShrink: 0 }}>
          <Tooltip title="Save">
            <IconButton
              size="small"
              onClick={onSaveClick}
              disabled={isLoading}
              sx={{ mr: 0.5 }}
            >
              <SaveIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Cancel">
            <IconButton
              size="small"
              onClick={onCancelClick}
              disabled={isLoading}
            >
              <CancelIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    )
  }

  return <>{children}</>
}
