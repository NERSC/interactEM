import { Add as AddIcon } from "@mui/icons-material"
import {
  Box,
  Button,
  CircularProgress,
  Divider,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type React from "react" // Added useRef
import { useEffect, useRef, useState } from "react"
import InfiniteScroll from "react-infinite-scroll-component"
import type { PipelinePublic } from "../client"
import {
  pipelinesCreatePipelineMutation,
  pipelinesReadPipelinesQueryKey,
} from "../client/generated/@tanstack/react-query.gen"
import { useInfinitePipelines } from "../hooks/usePipelinesQuery"
import type { PipelineJSON } from "../pipeline"
import { usePipelineStore } from "../stores"

interface PipelineListProps {
  open: boolean
  onClose: () => void
  onPipelineSelect: (pipeline: PipelineJSON) => void
}

export const PipelineList: React.FC<PipelineListProps> = ({
  open,
  onClose,
  onPipelineSelect,
}) => {
  const queryClient = useQueryClient()
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(false)

  const {
    data: pipelineData,
    fetchNextPage: fetchNextPipelines,
    hasNextPage: hasNextPipelines,
    isLoading: isLoadingPipelines,
    isError: isErrorPipelines,
    error: errorPipelines,
  } = useInfinitePipelines()

  // Mutation hook for creating a new pipeline
  const createPipeline = useMutation({
    ...pipelinesCreatePipelineMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
    },
    onError: (error) => {
      console.error("Failed to create pipeline:", error)
    },
  })

  const currentPipelineId = usePipelineStore((state) => state.currentPipelineId)
  const setCurrentPipelineId = usePipelineStore(
    (state) => state.setCurrentPipelineId,
  )

  const pipelines = pipelineData?.pages.flatMap((page) => page.data) ?? []
  const pipelineScrollTargetId = "pipeline-drawer-scroll-target"

  // Check for scroll and load more content if needed
  const checkAndLoadMore = () => {
    if (loading || !hasNextPipelines || !containerRef.current) return

    const container = containerRef.current
    const containerHeight = container.clientHeight
    const contentHeight = container.scrollHeight

    // If content doesn't fill container, load more
    if (contentHeight <= containerHeight && hasNextPipelines) {
      console.log("Loading more pipelines - content doesn't fill container")
      setLoading(true)
      fetchNextPipelines().finally(() => setLoading(false))
    }
  }

  // When drawer opens or pipelines data changes
  useEffect(() => {
    if (!open || isLoadingPipelines) return

    // Use setTimeout to ensure DOM has updated
    const timer = setTimeout(() => {
      checkAndLoadMore()
    }, 100)

    return () => clearTimeout(timer)
  }, [open, pipelineData, isLoadingPipelines])

  // Load more when drawer resizes
  useEffect(() => {
    if (!open) return

    const handleResize = () => {
      checkAndLoadMore()
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [open, hasNextPipelines])

  const handleSelectPipeline = (pipeline: PipelinePublic) => {
    setCurrentPipelineId(pipeline.id)
    if (pipeline.data && typeof pipeline.data === "object") {
      onPipelineSelect({ data: pipeline.data })
    } else {
      console.warn(
        "Selected pipeline has missing or invalid data structure, using empty default:",
        pipeline,
      )
      onPipelineSelect({ data: {} })
    }
    onClose()
  }

  const handleCreateNewPipeline = () => {
    createPipeline.mutate({
      body: { data: {} },
    })
  }

  const pipelineLoader = (
    <Box sx={{ display: "flex", justifyContent: "center", p: 1 }}>
      <CircularProgress size={20} />
    </Box>
  )

  const pipelineEndMessage = (
    <Typography
      variant="caption"
      display="block"
      textAlign="center"
      sx={{ p: 1 }}
    >
      {pipelines.length > 0 ? "No more pipelines" : "No pipelines found"}
    </Typography>
  )

  return (
    <Drawer anchor="left" open={open} onClose={onClose}>
      <Box
        sx={{ width: 300, height: "100%", overflow: "hidden" }}
        role="presentation"
      >
        <Box sx={{ p: 2, display: "flex", justifyContent: "space-between" }}>
          <Typography variant="h6">Pipelines</Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddIcon />}
            onClick={handleCreateNewPipeline}
            disabled={createPipeline.isPending}
          >
            New
          </Button>
        </Box>
        <Divider />
        <Box
          ref={containerRef} // Use ref here
          id={pipelineScrollTargetId}
          sx={{ height: "calc(100% - 76px)", overflowY: "auto" }}
        >
          {isErrorPipelines && (
            <Typography color="error" sx={{ p: 2 }}>
              Error loading pipelines: {errorPipelines?.message}
            </Typography>
          )}

          <InfiniteScroll
            dataLength={pipelines.length}
            next={fetchNextPipelines}
            hasMore={hasNextPipelines ?? false}
            loader={loading || isLoadingPipelines ? pipelineLoader : null}
            scrollableTarget={pipelineScrollTargetId}
            endMessage={pipelineEndMessage}
            style={{ overflow: "visible" }} // Prevent double scrollbars
          >
            <List disablePadding>
              {pipelines.map((pipeline) => (
                <ListItem
                  key={pipeline.id}
                  disablePadding
                  sx={{
                    backgroundColor:
                      currentPipelineId === pipeline.id
                        ? "action.selected"
                        : "inherit",
                  }}
                >
                  <ListItemButton
                    onClick={() => handleSelectPipeline(pipeline)}
                  >
                    <ListItemText
                      primary={`Pipeline ${pipeline.id.substring(0, 8)}...`}
                      secondary={`Updated: ${new Date(
                        pipeline.updated_at,
                      ).toLocaleString()}`}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </InfiniteScroll>

          {isLoadingPipelines && pipelines.length === 0 && pipelineLoader}
        </Box>
      </Box>
    </Drawer>
  )
}
