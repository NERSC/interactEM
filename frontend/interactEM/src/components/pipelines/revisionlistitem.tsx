import EditIcon from "@mui/icons-material/Edit"
import { IconButton, ListItem, ListItemText, Tooltip } from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { useState } from "react"
import type React from "react"
import type { PipelineRevisionPublic } from "../../client"
import {
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesUpdatePipelineRevisionMutation,
} from "../../client/generated/@tanstack/react-query.gen"
import { useInlineEdit } from "../../hooks/useInlineEdit"
import { usePipelineStore } from "../../stores"
import { InlineEditField } from "./inlineediffield"

interface RevisionListItemProps {
  revision: PipelineRevisionPublic
  onSelect: (revision: PipelineRevisionPublic) => void
}

export const RevisionListItem: React.FC<RevisionListItemProps> = ({
  revision,
  onSelect,
}) => {
  const queryClient = useQueryClient()
  const { currentRevisionId } = usePipelineStore()
  const isSelected = currentRevisionId === revision.revision_id
  const [isEditing, setIsEditing] = useState(false)

  const updateRevisionTag = useMutation({
    ...pipelinesUpdatePipelineRevisionMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: pipelinesListPipelineRevisionsQueryKey({
          path: { id: revision.pipeline_id },
        }),
      })
      setIsEditing(false)
    },
    onError: (error) => {
      console.error("Failed to update revision tag:", error)
    },
  })

  const {
    value,
    handleEditClick,
    handleCancelClick,
    handleValueChange,
    handleKeyDown,
  } = useInlineEdit({
    initialValue: revision.tag ?? "",
    onEditingChange: setIsEditing,
    onSave: (newTag) => {
      updateRevisionTag.mutate({
        path: { id: revision.pipeline_id, revision_id: revision.revision_id },
        body: { tag: newTag || null },
      })
    },
  })

  const handleSelect = () => {
    if (!isEditing) {
      onSelect(revision)
    }
  }

  const handleSaveClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    updateRevisionTag.mutate({
      path: { id: revision.pipeline_id, revision_id: revision.revision_id },
      body: { tag: value || null },
    })
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
      <InlineEditField
        isEditing={isEditing}
        value={value}
        onChange={handleValueChange}
        onKeyDown={handleKeyDown}
        onSaveClick={handleSaveClick}
        onCancelClick={handleCancelClick}
        isLoading={updateRevisionTag.isPending}
      >
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
      </InlineEditField>
    </ListItem>
  )
}
