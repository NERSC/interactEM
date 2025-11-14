import EditIcon from "@mui/icons-material/Edit"
import {
  Box,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemText,
  Tooltip,
} from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { useState } from "react"
import type { PipelinePublic } from "../../client"
import {
  pipelinesReadPipelineQueryKey,
  pipelinesReadPipelinesQueryKey,
  pipelinesUpdatePipelineMutation,
} from "../../client/generated/@tanstack/react-query.gen"
import { useInlineEdit } from "../../hooks/useInlineEdit"
import { usePipelineStore } from "../../stores"
import { DeletePipelineButton } from "./deletebutton"
import { DuplicatePipelineButton } from "./duplicatebutton"
import { InlineEditField } from "./inlineediffield"

interface PipelineListItemProps {
  pipeline: PipelinePublic
  onSelect?: () => void
}

export const PipelineListItem = ({
  pipeline,
  onSelect,
}: PipelineListItemProps) => {
  const { currentPipelineId, setPipeline } = usePipelineStore()
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)

  const updatePipelineMutation = useMutation({
    ...pipelinesUpdatePipelineMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelineQueryKey({
          path: { id: pipeline.id },
        }),
      })
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      setIsEditing(false)
    },
  })

  const {
    value,
    handleEditClick,
    handleCancelClick,
    handleValueChange,
    handleKeyDown,
  } = useInlineEdit({
    initialValue: pipeline.name || "",
    onEditingChange: setIsEditing,
    onSave: (newName) => {
      updatePipelineMutation.mutate({
        path: { id: pipeline.id },
        body: { name: newName },
      })
    },
  })

  const handleListItemClick = () => {
    if (!isEditing) {
      setPipeline(pipeline)
      if (onSelect) onSelect()
    }
  }

  const handleSaveClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    updatePipelineMutation.mutate({
      path: { id: pipeline.id },
      body: { name: value },
    })
  }

  const isSelected = currentPipelineId === pipeline.id
  const displayName = pipeline.name || pipeline.id.substring(0, 8)
  const lastUpdated = `${formatDistanceToNow(new Date(pipeline.updated_at))} ago`
  const isMutating = updatePipelineMutation.isPending

  return (
    <ListItem
      disablePadding
      onClick={handleListItemClick}
      sx={{
        backgroundColor: isSelected ? "action.selected" : "inherit",
        display: "flex",
        alignItems: "center",
        "&:hover .pipeline-buttons": {
          opacity: 1,
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
        isLoading={isMutating}
      >
        <ListItemButton sx={{ flex: 1, overflow: "hidden" }}>
          <ListItemText
            primary={displayName}
            secondary={`Updated ${lastUpdated}`}
            sx={{ overflow: "hidden", textOverflow: "ellipsis" }}
          />
        </ListItemButton>
        <Box
          className="pipeline-buttons"
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0,
            pr: 1,
            flexShrink: 0,
            opacity: 0,
            transition: "opacity 0.2s ease-in-out",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Tooltip title="Edit Pipeline Name">
            <IconButton
              size="small"
              onClick={handleEditClick}
              disabled={isMutating}
              color="inherit"
              sx={{ mr: 0.5 }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <DuplicatePipelineButton pipelineId={pipeline.id} />
          <DeletePipelineButton
            pipelineId={pipeline.id}
            pipelineName={displayName}
          />
        </Box>
      </InlineEditField>
    </ListItem>
  )
}
