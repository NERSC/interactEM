import CancelIcon from "@mui/icons-material/Cancel"
import EditIcon from "@mui/icons-material/Edit"
import SaveIcon from "@mui/icons-material/Save"
import {
  Box,
  IconButton,
  ListItem,
  ListItemText,
  TextField,
  Tooltip,
} from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import type React from "react"
import { useState } from "react"
import type { PipelineRevisionPublic } from "../client"
import {
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesUpdatePipelineRevisionMutation,
} from "../client/generated/@tanstack/react-query.gen"
import { usePipelineStore } from "../stores"

interface RevisionListItemProps {
  revision: PipelineRevisionPublic
  onSelect: (revision: PipelineRevisionPublic) => void
}

export const RevisionListItem: React.FC<RevisionListItemProps> = ({
  revision,
  onSelect,
}) => {
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [tagValue, setTagValue] = useState(revision.tag ?? "")
  const { currentRevisionId } = usePipelineStore()
  const isSelected = currentRevisionId === revision.revision_id

  const updateRevisionTag = useMutation({
    ...pipelinesUpdatePipelineRevisionMutation(),
    onSuccess: () => {
      // Invalidate the revisions list query to refetch
      queryClient.invalidateQueries({
        queryKey: pipelinesListPipelineRevisionsQueryKey({
          path: { id: revision.pipeline_id },
        }),
      })
      setIsEditing(false)
    },
    onError: (error) => {
      console.error("Failed to update revision tag:", error)
      // Restore original value on error
      setTagValue(revision.tag ?? "")
      setIsEditing(false)
    },
  })

  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsEditing(true)
  }

  const handleSaveClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    updateRevisionTag.mutate({
      path: { id: revision.pipeline_id, revision_id: revision.revision_id },
      body: { tag: tagValue || null },
    })
  }

  const handleCancelClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setTagValue(revision.tag ?? "")
    setIsEditing(false)
  }

  const handleTagChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTagValue(e.target.value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      updateRevisionTag.mutate({
        path: { id: revision.pipeline_id, revision_id: revision.revision_id },
        body: { tag: tagValue || null },
      })
    } else if (e.key === "Escape") {
      setTagValue(revision.tag ?? "")
      setIsEditing(false)
    }
  }

  const handleSelect = () => {
    if (!isEditing) {
      onSelect(revision)
    }
  }

  const displayLabel = revision.tag || `Revision ${revision.revision_id}`
  const displayDate = `${formatDistanceToNow(new Date(revision.created_at))} ago`

  return (
    <ListItem
      onClick={handleSelect}
      sx={{
        pl: 2,
        pr: 2,
        bgcolor: isSelected ? "action.selected" : "inherit",
        "&:hover": {
          bgcolor: isSelected ? "action.selected" : "action.hover",
        },
      }}
    >
      {isEditing ? (
        <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
          <TextField
            value={tagValue}
            onChange={handleTagChange}
            onKeyDown={handleKeyDown}
            variant="standard"
            size="small"
            fullWidth
            autoFocus
            onClick={(e) => e.stopPropagation()}
          />
          <Box sx={{ display: "flex", ml: 1 }}>
            <Tooltip title="Save">
              <IconButton
                size="small"
                onClick={handleSaveClick}
                disabled={updateRevisionTag.isPending}
                sx={{ mr: 0.5 }}
              >
                <SaveIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Cancel">
              <IconButton
                size="small"
                onClick={handleCancelClick}
                disabled={updateRevisionTag.isPending}
              >
                <CancelIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      ) : (
        <>
          <ListItemText primary={displayLabel} secondary={displayDate} />
          <Tooltip title="Edit Tag">
            <IconButton
              edge="end"
              aria-label="edit"
              onClick={handleEditClick}
              size="small"
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      )}
    </ListItem>
  )
}
