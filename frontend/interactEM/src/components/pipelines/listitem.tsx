import { Box, ListItem, ListItemButton, ListItemText } from "@mui/material"
import { formatDistanceToNow } from "date-fns"
import type { PipelinePublic } from "../../client"
import { usePipelineStore } from "../../stores"
import { DeletePipelineButton } from "./deletebutton"
import { DuplicatePipelineButton } from "./duplicatebutton"

interface PipelineListItemProps {
  pipeline: PipelinePublic
  onSelect?: () => void
}

export const PipelineListItem = ({
  pipeline,
  onSelect,
}: PipelineListItemProps) => {
  const { currentPipelineId, setPipeline } = usePipelineStore()

  const handleListItemClick = () => {
    setPipeline(pipeline)
    if (onSelect) onSelect()
  }

  const isSelected = currentPipelineId === pipeline.id
  const displayName = pipeline.name || pipeline.id.substring(0, 8)
  const lastUpdated = `${formatDistanceToNow(new Date(pipeline.updated_at))} ago`

  return (
    <ListItem
      disablePadding
      sx={{
        backgroundColor: isSelected ? "action.selected" : "inherit",
        display: "flex",
        alignItems: "center",
      }}
    >
      <ListItemButton
        onClick={handleListItemClick}
        sx={{ flex: 1, overflow: "hidden" }}
      >
        <ListItemText
          primary={displayName}
          secondary={`Updated ${lastUpdated}`}
          sx={{ overflow: "hidden", textOverflow: "ellipsis" }}
        />
      </ListItemButton>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          pr: 1,
          flexShrink: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <DuplicatePipelineButton pipelineId={pipeline.id} />
        <DeletePipelineButton
          pipelineId={pipeline.id}
          pipelineName={displayName}
        />
      </Box>
    </ListItem>
  )
}
