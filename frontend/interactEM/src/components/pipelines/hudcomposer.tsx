import HistoryIcon from "@mui/icons-material/History"
import ListIcon from "@mui/icons-material/List"
import {
  Box,
  CircularProgress,
  Divider,
  IconButton,
  Popover,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material"
import { CommitIcon } from "@radix-ui/react-icons"
import { useCallback, useRef, useState } from "react"
import { useActivePipeline } from "../../hooks/api/useActivePipeline"
import { usePipelineStore } from "../../stores"
import { DeletePipelineButton } from "./deletebutton"
import { HudListButton } from "./hudlistbutton"
import { LaunchPipelineButton } from "./launchbutton"
import { PipelineList } from "./list"
import { RevisionList } from "./revisionlist"
import { ViewModeToggle } from "./viewmodetoggle"

export const HudComposer: React.FC = () => {
  const { currentPipelineId, currentRevisionId, setCurrentRevisionId } =
    usePipelineStore()
  const [isRevisionPopoverOpen, setIsRevisionPopoverOpen] = useState(false)
  const [isPipelineDrawerOpen, setIsPipelineDrawerOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const revisionButtonRef = useRef<HTMLButtonElement | null>(null)

  const { pipeline, isLoading } = useActivePipeline()

  // Pipeline List Drawer handlers
  const handleTogglePipelineDrawer = useCallback(() => {
    setIsPipelineDrawerOpen(!isPipelineDrawerOpen)
  }, [isPipelineDrawerOpen])

  const handleClosePipelineDrawer = useCallback(() => {
    setIsPipelineDrawerOpen(false)
  }, [])

  // Revision List handlers
  const revisionListId = isRevisionPopoverOpen ? "revision-popover" : undefined

  const handleToggleRevisionPopover = () => {
    setIsRevisionPopoverOpen(!isRevisionPopoverOpen)
  }

  const handleCloseRevisionPopover = () => {
    setIsRevisionPopoverOpen(false)
  }

  const handleRevisionSelected = (revisionId: number) => {
    setCurrentRevisionId(revisionId)
    handleCloseRevisionPopover()
  }

  const isMutating = isDeleting

  // Pipeline content rendering
  const pipelineDisplayContent = () => {
    if (!currentPipelineId) {
      return (
        <Typography variant="body2" color="text.secondary">
          No pipeline selected
        </Typography>
      )
    }

    if (isLoading) {
      return <CircularProgress size={24} />
    }

    if (!pipeline) {
      return (
        <Typography variant="body2" color="error">
          Error loading pipeline.
        </Typography>
      )
    }

    const displayName = pipeline.name || pipeline.id.substring(0, 8)

    return (
      <>
        <Stack direction="column" sx={{ flexGrow: 1, mr: 1 }}>
          <Typography
            variant="subtitle1"
            fontWeight="medium"
            noWrap
            sx={{ display: "flex", alignItems: "center", gap: 1 }}
          >
            {displayName}
            <Box
              component="span"
              sx={{
                display: "flex",
                alignItems: "center",
                bgcolor: "rgba(0, 0, 0, 0.05)",
                borderRadius: "4px",
                px: 0.8,
                py: 0.2,
                ml: 0.5,
                color: "text.secondary",
                fontSize: "0.8em",
              }}
            >
              <Box component="span" sx={{ mr: 0.5, display: "flex" }}>
                <CommitIcon fontSize="small" />
              </Box>
              {currentRevisionId}
            </Box>
          </Typography>
        </Stack>
        <DeletePipelineButton
          pipelineId={pipeline.id}
          pipelineName={displayName}
          disabled={isMutating && !isDeleting}
          onDeleteStarted={() => setIsDeleting(true)}
          onDeleteFinished={() => setIsDeleting(false)}
        />
        <LaunchPipelineButton disabled={isMutating} />
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Tooltip title="Revision History">
          <span>
            <IconButton
              ref={revisionButtonRef}
              size="small"
              onClick={handleToggleRevisionPopover}
              aria-describedby={revisionListId}
              disabled={isMutating}
            >
              <HistoryIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </>
    )
  }

  return (
    <>
      <Box
        sx={{
          p: 1,
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: 1,
          minWidth: 300,
          display: "flex",
          alignItems: "center",
        }}
      >
        {/* View Mode Toggle */}
        <ViewModeToggle />

        {/* Pipeline List Toggle Button */}
        <HudListButton
          tooltip="Pipeline List"
          icon={<ListIcon fontSize="small" />}
          onClick={handleTogglePipelineDrawer}
        />

        <Divider orientation="vertical" flexItem sx={{ mr: 1 }} />

        {/* Pipeline content */}
        {pipelineDisplayContent()}
      </Box>

      {/* Pipeline List Drawer */}
      <PipelineList
        open={isPipelineDrawerOpen}
        onClose={handleClosePipelineDrawer}
      />

      {/* Revision List Popover */}
      <Popover
        id={revisionListId}
        open={isRevisionPopoverOpen}
        anchorEl={revisionButtonRef.current}
        onClose={handleCloseRevisionPopover}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
      >
        <RevisionList onRevisionSelect={handleRevisionSelected} />
      </Popover>
    </>
  )
}
