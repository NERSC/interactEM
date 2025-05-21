import { ListItem, ListItemButton, ListItemText } from "@mui/material"
import { formatDistanceToNow } from "date-fns"
import type { PipelinePublic } from "../../client"
import { usePipelineStore } from "../../stores"

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
      }}
    >
      <ListItemButton onClick={handleListItemClick}>
        <ListItemText
          primary={displayName}
          secondary={`Updated ${lastUpdated}`}
          sx={{ overflow: "hidden", textOverflow: "ellipsis" }}
        />
      </ListItemButton>
    </ListItem>
  )
}
