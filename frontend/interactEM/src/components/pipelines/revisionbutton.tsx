import { Box, Tooltip } from "@mui/material"
import { CommitIcon } from "@radix-ui/react-icons"
import { forwardRef } from "react"

interface RevisionButtonProps {
  revisionId: number | null
  onClick?: () => void
}

export const RevisionButton = forwardRef<
  HTMLButtonElement,
  RevisionButtonProps
>(({ revisionId, onClick }, ref) => {
  if (revisionId === null) {
    return null
  }

  const isDisabled = !onClick

  return (
    <Tooltip title={isDisabled ? undefined : "View Revision History"}>
      <Box
        ref={ref}
        component="button"
        onClick={onClick}
        disabled={isDisabled}
        sx={{
          display: "flex",
          alignItems: "center",
          bgcolor: "rgba(0, 0, 0, 0.05)",
          borderRadius: "4px",
          px: 0.8,
          py: 0.2,
          color: "text.secondary",
          fontSize: "0.8em",
          border: "none",
          cursor: isDisabled ? "default" : "pointer",
          opacity: isDisabled ? 0.6 : 1,
          transition: "background-color 0.2s ease-in-out",
          "&:hover:not(:disabled)": {
            bgcolor: "rgba(0, 0, 0, 0.1)",
          },
        }}
      >
        <Box component="span" sx={{ mr: 0.5, display: "flex" }}>
          <CommitIcon fontSize="small" />
        </Box>
        {revisionId}
      </Box>
    </Tooltip>
  )
})
