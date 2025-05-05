import { Edit } from "@mui/icons-material"
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
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useCallback, useRef, useState } from "react"
import {
  pipelinesReadPipelineQueryKey,
  pipelinesReadPipelinesQueryKey,
  pipelinesUpdatePipelineMutation,
} from "../client"
import { useActivePipeline } from "../hooks/useActivePipeline"
import { usePipelineContext } from "../hooks/usePipelineContext"
import { usePipelineStore } from "../stores"
import { LaunchPipelineButton } from "./launchpipelinebutton"
import { DeletePipelineButton } from "./pipelinedeletebutton"
import { PipelineEditDialog } from "./pipelineeditdialog"
import { PipelineList } from "./pipelinelist"
import { RevisionList } from "./revisionlist"
import { StopPipelineButton } from "./stoppipelinebutton"

export const PipelineHud: React.FC = () => {
  const queryClient = useQueryClient()
  const { currentPipelineId, currentRevisionId, setCurrentRevisionId } =
    usePipelineStore()
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isRevisionPopoverOpen, setIsRevisionPopoverOpen] = useState(false)
  const [isPipelineDrawerOpen, setIsPipelineDrawerOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const revisionButtonRef = useRef<HTMLButtonElement | null>(null)

  const { pipeline, isLoading } = useActivePipeline()
  const { isCurrentPipelineRunning } = usePipelineContext()

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

  // Edit Dialog handlers
  const handleOpenEditDialog = () => {
    setIsEditDialogOpen(true)
  }

  const handleCloseEditDialog = () => {
    setIsEditDialogOpen(false)
  }

  const updatePipelineMutation = useMutation({
    ...pipelinesUpdatePipelineMutation(),
    onSuccess: (updatedPipeline) => {
      handleCloseEditDialog()
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelineQueryKey({
          path: { id: updatedPipeline.id },
        }),
      })
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
    },
    onError: () => handleCloseEditDialog(),
  })

  const handleSaveEdit = (newName: string) => {
    if (!pipeline) return
    updatePipelineMutation.mutate({
      path: { id: pipeline.id },
      body: { name: newName },
    })
  }

  const isMutating = updatePipelineMutation.isPending || isDeleting

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
        <Tooltip title="Edit Pipeline Name">
          <span>
            <IconButton
              size="small"
              onClick={handleOpenEditDialog}
              disabled={isMutating}
              sx={{ mr: 0.5 }}
            >
              <Edit fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        {!isCurrentPipelineRunning && (
          <DeletePipelineButton
            pipelineId={pipeline.id}
            pipelineName={displayName}
            disabled={isMutating && !isDeleting}
            onDeleteStarted={() => setIsDeleting(true)}
            onDeleteFinished={() => setIsDeleting(false)}
          />
        )}
        {isCurrentPipelineRunning ? (
          <StopPipelineButton disabled={isMutating} />
        ) : (
          <LaunchPipelineButton disabled={isMutating} />
        )}
        {!isCurrentPipelineRunning && (
          <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        )}
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
        {/* Pipeline List Toggle Button */}
        <Tooltip title="Pipeline List">
          <IconButton
            size="small"
            onClick={handleTogglePipelineDrawer}
            sx={{ mr: 1 }}
          >
            <ListIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        {/* Show separating divider */}
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

      {/* Edit Dialog */}
      {pipeline && (
        <PipelineEditDialog
          open={isEditDialogOpen}
          onClose={handleCloseEditDialog}
          onSave={handleSaveEdit}
          initialName={pipeline.name ?? ""}
          isSaving={updatePipelineMutation.isPending}
        />
      )}
    </>
  )
}
