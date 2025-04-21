import { Edit } from "@mui/icons-material"
import HistoryIcon from "@mui/icons-material/History"
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
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { useCallback, useRef, useState } from "react"
import {
  pipelinesReadPipelineQueryKey,
  pipelinesReadPipelinesQueryKey,
  pipelinesUpdatePipelineMutation,
} from "../client/generated/@tanstack/react-query.gen"
import { useActivePipeline } from "../hooks/useActivePipeline"
import { usePipelineStore } from "../stores"
import { LaunchPipelineButton } from "./launchpipelinebutton"
import { DeletePipelineButton } from "./pipelinedeletebutton"
import { PipelineEditDialog } from "./pipelineeditdialog"
import { RevisionList } from "./revisionlist"

export const CurrentPipelineDisplay: React.FC = () => {
  const queryClient = useQueryClient()
  const { currentPipelineId, setCurrentRevisionId } = usePipelineStore()
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isRevisionPopoverOpen, setIsRevisionPopoverOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false) // State to track deletion status
  const revisionButtonRef = useRef<HTMLButtonElement | null>(null)

  const { pipeline, isLoading } = useActivePipeline()

  const updatePipelineMutation = useMutation({
    ...pipelinesUpdatePipelineMutation(),
    onSuccess: (updatedPipeline) => {
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      queryClient.setQueryData(
        pipelinesReadPipelineQueryKey({ path: { id: updatedPipeline.id } }),
        updatedPipeline,
      )
      setIsEditDialogOpen(false)
    },
    onError: () => setIsEditDialogOpen(false),
  })

  const handleOpenEditDialog = () => setIsEditDialogOpen(true)
  const handleCloseEditDialog = () => setIsEditDialogOpen(false)
  const handleSaveEdit = (newName: string) => {
    if (!pipeline) return
    updatePipelineMutation.mutate({
      path: { id: pipeline.id },
      body: { name: newName || null },
    })
  }

  const handleToggleRevisionPopover = () =>
    setIsRevisionPopoverOpen((prev) => !prev)

  const handleCloseRevisionPopover = useCallback(
    () => setIsRevisionPopoverOpen(false),
    [],
  )

  const handleRevisionSelected = useCallback(
    (revisionId: number) => {
      setCurrentRevisionId(revisionId)
      handleCloseRevisionPopover()
    },
    [setCurrentRevisionId, handleCloseRevisionPopover],
  )

  const revisionListId = isRevisionPopoverOpen ? "revision-popover" : undefined
  const isMutating = updatePipelineMutation.isPending || isDeleting
  if (!currentPipelineId) {
    return (
      <Box
        sx={{
          p: 1,
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: 1,
          minWidth: 250,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 56,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          No pipeline selected
        </Typography>
      </Box>
    )
  }

  if (isLoading) {
    return (
      <Box
        sx={{
          p: 1,
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: 1,
          minWidth: 250,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 56,
        }}
      >
        <CircularProgress size={24} />
      </Box>
    )
  }

  if (!pipeline) {
    return (
      <Box
        sx={{
          p: 1,
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: 1,
          minWidth: 250,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 56,
        }}
      >
        <Typography variant="body2" color="error">
          Error loading pipeline.
        </Typography>
      </Box>
    )
  }

  const displayName = pipeline.name || pipeline.id.substring(0, 8)
  const displayRevision = pipeline.current_revision_id
  const lastUpdated = `${formatDistanceToNow(new Date(pipeline.updated_at))} ago`

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
        <Stack direction="column" sx={{ flexGrow: 1, mr: 1 }}>
          <Tooltip title={pipeline.name ? `ID: ${pipeline.id}` : ""}>
            <Typography variant="subtitle1" fontWeight="medium" noWrap>
              {displayName}
            </Typography>
          </Tooltip>
          <Typography variant="caption" color="text.secondary" noWrap>
            {displayRevision} &bull; Updated {lastUpdated}
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
      </Box>

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
