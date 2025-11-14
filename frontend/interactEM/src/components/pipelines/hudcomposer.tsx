import ListIcon from "@mui/icons-material/List"
import {
  Box,
  CircularProgress,
  Popover,
  Stack,
  Typography,
} from "@mui/material"
import { useCallback, useRef, useState } from "react"
import { useActivePipeline } from "../../hooks/api/useActivePipeline"
import { usePipelineStore } from "../../stores"
import { DeletePipelineButton } from "./deletebutton"
import { HudListButton } from "./hudlistbutton"
import { LaunchPipelineButton } from "./launchbutton"
import { PipelineList } from "./list"
import { RevisionButton } from "./revisionbutton"
import { RevisionList } from "./revisionlist"

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
        <Stack direction="row" alignItems="center" sx={{ gap: 0.5, flex: 1 }}>
          <Typography
            variant="subtitle1"
            fontWeight="medium"
            noWrap
            sx={{ display: "flex", alignItems: "center" }}
          >
            {displayName}
          </Typography>
          <RevisionButton
            ref={revisionButtonRef}
            revisionId={currentRevisionId}
            onClick={isMutating ? undefined : handleToggleRevisionPopover}
          />
          <DeletePipelineButton
            pipelineId={pipeline.id}
            pipelineName={displayName}
            disabled={isMutating && !isDeleting}
            onDeleteStarted={() => setIsDeleting(true)}
            onDeleteFinished={() => setIsDeleting(false)}
          />
          <LaunchPipelineButton disabled={isMutating} />
        </Stack>
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
          display: "flex",
          alignItems: "center",
          gap: 0.5,
        }}
      >
        {/* Pipeline List Toggle Button */}
        <HudListButton
          tooltip="Pipeline List"
          icon={<ListIcon fontSize="small" />}
          onClick={handleTogglePipelineDrawer}
        />

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
