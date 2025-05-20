import {
  Box,
  CircularProgress,
  Divider,
  Drawer,
  List,
  Typography,
} from "@mui/material"
import { useCallback, useEffect, useRef } from "react"
import InfiniteScroll from "react-infinite-scroll-component"
import { useInfinitePipelines } from "../../hooks/usePipelinesQuery"
import { PipelineListItem } from "./listitem"
import { NewPipelineButton } from "./newbutton"

interface PipelineListProps {
  open: boolean
  onClose: () => void
}

export const PipelineList: React.FC<PipelineListProps> = ({
  open,
  onClose,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)

  const {
    data: pipelinesQueryData,
    fetchNextPage: fetchNextPipelines,
    hasNextPage: hasNextPipelines,
    isLoading: isLoadingPipelines,
    isError: isErrorPipelines,
    error: errorPipelines,
  } = useInfinitePipelines()

  const pipelines = pipelinesQueryData?.pages.flatMap((page) => page.data) ?? []
  const pipelineScrollTargetId = "pipeline-drawer-scroll-target"

  const checkAndLoadMore = useCallback(() => {
    if (!containerRef.current) return
    if (!hasNextPipelines) return

    const container = containerRef.current
    const containerHeight = container.clientHeight
    const contentHeight = container.scrollHeight

    if (contentHeight <= containerHeight) {
      console.log("Loading more pipelines - content doesn't fill container")
      fetchNextPipelines()
    }
  }, [hasNextPipelines, fetchNextPipelines])

  useEffect(() => {
    if (!open || isLoadingPipelines) return

    const timer = setTimeout(() => {
      checkAndLoadMore()
    }, 100)

    return () => clearTimeout(timer)
  }, [open, isLoadingPipelines, checkAndLoadMore])

  useEffect(() => {
    if (!open) return

    const handleResize = () => {
      checkAndLoadMore()
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [open, checkAndLoadMore])

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
          <NewPipelineButton />
        </Box>
        <Divider />
        <Box
          ref={containerRef}
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
            hasMore={hasNextPipelines}
            loader={isLoadingPipelines ? pipelineLoader : null}
            scrollableTarget={pipelineScrollTargetId}
            endMessage={pipelineEndMessage}
            style={{ overflow: "visible" }}
          >
            <List disablePadding>
              {pipelines.map((pipeline) => (
                <PipelineListItem
                  key={pipeline.id}
                  pipeline={pipeline}
                  onSelect={onClose}
                />
              ))}
            </List>
          </InfiniteScroll>

          {isLoadingPipelines && pipelines.length === 0 && pipelineLoader}
        </Box>
      </Box>
    </Drawer>
  )
}
