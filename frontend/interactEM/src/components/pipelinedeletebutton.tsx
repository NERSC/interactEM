import { Delete } from "@mui/icons-material"
import {
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Tooltip,
} from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type React from "react"
import { useState } from "react"
import {
  pipelinesDeletePipelineMutation,
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesReadPipelineQueryKey,
  pipelinesReadPipelinesQueryKey,
} from "../client/generated/@tanstack/react-query.gen"
import { usePipelineStore } from "../stores"

interface DeletePipelineButtonProps {
  pipelineId: string
  pipelineName: string
  disabled?: boolean
  onDeleteStarted?: () => void
  onDeleteFinished?: () => void
}

export const DeletePipelineButton: React.FC<DeletePipelineButtonProps> = ({
  pipelineId,
  pipelineName,
  disabled = false,
  onDeleteStarted,
  onDeleteFinished,
}) => {
  const queryClient = useQueryClient()
  const { setPipeline } = usePipelineStore()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const deletePipelineMutation = useMutation({
    ...pipelinesDeletePipelineMutation(),
    onMutate: () => {
      onDeleteStarted?.()
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      queryClient.removeQueries({
        queryKey: pipelinesReadPipelineQueryKey({
          path: { id: variables.path.id },
        }),
      })
      queryClient.removeQueries({
        queryKey: pipelinesListPipelineRevisionsQueryKey({
          path: { id: variables.path.id },
        }),
      })
      setPipeline(null)
      setShowDeleteConfirm(false)
      onDeleteFinished?.()
    },
    onError: () => {
      setShowDeleteConfirm(false)
      onDeleteFinished?.()
    },
  })

  const handleDeleteClick = () => setShowDeleteConfirm(true)
  const handleCloseDeleteConfirm = () => setShowDeleteConfirm(false)
  const handleConfirmDelete = () => {
    deletePipelineMutation.mutate({ path: { id: pipelineId } })
  }

  const isDeleting = deletePipelineMutation.isPending

  return (
    <>
      <Tooltip title="Delete Pipeline">
        <span>
          <IconButton
            size="small"
            onClick={handleDeleteClick}
            disabled={disabled || isDeleting}
            color="error"
            sx={{ mr: 0.5 }}
          >
            {isDeleting ? (
              <CircularProgress size={20} color="error" />
            ) : (
              <Delete fontSize="small" />
            )}
          </IconButton>
        </span>
      </Tooltip>

      <Dialog
        open={showDeleteConfirm}
        onClose={handleCloseDeleteConfirm}
        aria-labelledby="delete-confirm-dialog-title"
        aria-describedby="delete-confirm-dialog-description"
      >
        <DialogTitle id="delete-confirm-dialog-title">
          Confirm Deletion
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-confirm-dialog-description">
            Are you sure you want to delete the pipeline "{pipelineName}"? This
            will delete all its revisions and cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDeleteConfirm} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirmDelete}
            color="error"
            disabled={isDeleting}
            autoFocus
          >
            {isDeleting ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              "Delete"
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
