import { Box, CircularProgress, Divider, List, Typography } from "@mui/material"
import { useRef } from "react"
import InfiniteScroll from "react-infinite-scroll-component"
import { useInfinitePipelineRevisions } from "../../hooks/api/usePipelinesQuery"
import { usePipelineStore } from "../../stores"
import { RevisionListItem } from "./revisionlistitem"

interface RevisionListProps {
  onRevisionSelect: (revisionId: number) => void
}

export const RevisionList: React.FC<RevisionListProps> = ({
  onRevisionSelect,
}) => {
  const { currentPipelineId, setCurrentRevisionId } = usePipelineStore()
  const scrollableTargetId = "revision-list-scroll-target"
  const containerRef = useRef<HTMLDivElement>(null)

  const {
    data: revisionData,
    fetchNextPage,
    hasNextPage,
    isLoading,
    isError,
    error,
  } = useInfinitePipelineRevisions(currentPipelineId)

  const revisions = revisionData?.pages.flat() ?? []

  const handleSelectRevision = (revisionId: number) => {
    setCurrentRevisionId(revisionId)
    onRevisionSelect(revisionId)
  }

  const revisionLoader = (
    <Box sx={{ display: "flex", justifyContent: "center", p: 1 }}>
      <CircularProgress size={20} />
    </Box>
  )

  const revisionEndMessage = (
    <Typography
      variant="caption"
      display="block"
      textAlign="center"
      sx={{ p: 1 }}
    >
      {revisions.length > 0 ? "No more revisions" : "No revisions found"}
    </Typography>
  )

  if (!currentPipelineId) {
    return (
      <Box sx={{ width: 300, maxHeight: 400, overflow: "hidden" }}>
        <Typography variant="body2" color="textSecondary" sx={{ p: 2 }}>
          Select a pipeline to view its history.
        </Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{ width: 300, maxHeight: 400, overflow: "hidden" }}
      ref={containerRef}
    >
      <Box sx={{ p: 1.5 }}>
        <Typography variant="h6" fontSize="1.1rem">
          Revision History
        </Typography>
      </Box>
      <Divider />
      <Box
        id={scrollableTargetId}
        sx={{ height: "calc(400px - 50px)", overflowY: "auto" }}
      >
        {isError && (
          <Typography color="error" sx={{ p: 2 }}>
            Error loading revisions: {error?.message}
          </Typography>
        )}

        <InfiniteScroll
          dataLength={revisions.length}
          next={fetchNextPage}
          hasMore={hasNextPage ?? false}
          loader={isLoading ? revisionLoader : null}
          scrollableTarget={scrollableTargetId}
          endMessage={!isLoading ? revisionEndMessage : null}
          style={{ overflow: "visible" }}
        >
          <List disablePadding dense>
            {revisions.map((revision) => (
              <RevisionListItem
                key={`${revision.pipeline_id}-${revision.revision_id}`}
                revision={revision}
                onSelect={() => handleSelectRevision(revision.revision_id)}
              />
            ))}
          </List>
        </InfiniteScroll>

        {isLoading && revisions.length === 0 && revisionLoader}
      </Box>
    </Box>
  )
}
