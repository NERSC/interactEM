import { Box, CircularProgress, List, Typography } from "@mui/material"
import { useEffect, useRef } from "react"
import InfiniteScroll from "react-infinite-scroll-component"
import type { PipelineDeploymentPublic } from "../../client"
import { useInfiniteActiveDeployments, useInfiniteDeployments, useInfinitePipelineDeployments } from "../../hooks/api/useDeploymentsQuery"
import { DeploymentItem } from "./deploymentitem"

export type DeploymentsListVariant = "all" | "active" | "pipeline"

interface DeploymentsListProps {
  variant: DeploymentsListVariant
  pipelineId?: string | null
  showPipelineInfo?: boolean
  onDeploymentClick?: (deployment: PipelineDeploymentPublic) => void
  emptyMessage?: string
}

export const DeploymentsList: React.FC<DeploymentsListProps> = ({
  variant,
  pipelineId,
  showPipelineInfo = false,
  onDeploymentClick,
  emptyMessage = "No deployments found",
}) => {
  const scrollableTargetId = `${variant}-deployments-list-scroll-target`
  const containerRef = useRef<HTMLDivElement>(null)

  // Only call the query we actually need based on variant
  const query =
    variant === "pipeline"
      ? useInfinitePipelineDeployments(pipelineId ?? null)
      : variant === "active"
        ? useInfiniteActiveDeployments()
        : useInfiniteDeployments()

  const {
    data: deploymentsData,
    fetchNextPage,
    hasNextPage,
    isPending,
    isError,
    error,
  } = query
  console.log(
    "isLoading: ",
    query.isLoading,
    "isPending: ",
    isPending,
    "hasNextPage: ",
    hasNextPage,
  )

  const deployments = deploymentsData?.pages.flatMap((page) => page?.data || []) ?? []

  // Effect to fetch more if content doesn't fill the view.
  useEffect(() => {
    const checkAndFetch = () => {
      const target = document.getElementById(scrollableTargetId)
      // If the scrollable target exists, isn't scrollable, and has more pages, fetch the next page.
      if (target && target.scrollHeight <= target.clientHeight && hasNextPage) {
        fetchNextPage()
      }
    }

    // Check after a short delay to allow the DOM to update after rendering.
    const timeoutId = setTimeout(checkAndFetch, 100)

    // Cleanup the timeout on component unmount or dependency change.
    return () => clearTimeout(timeoutId)
  }, [hasNextPage, fetchNextPage, scrollableTargetId])

  const deploymentLoader = (
    <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
      <CircularProgress size={24} />
    </Box>
  )

  const deploymentEndMessage = (
    <Typography
      variant="caption"
      display="block"
      textAlign="center"
      sx={{ p: 2 }}
    >
      {deployments.length > 0 ? "No more deployments" : emptyMessage}
    </Typography>
  )

  // Handle pipeline variant with no pipeline selected
  if (variant === "pipeline" && !pipelineId) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
        Select a pipeline to view its deployments
      </Typography>
    )
  }

  if (isError) {
    return (
      <Typography color="error" sx={{ p: 2 }}>
        Error loading deployments: {error?.message}
      </Typography>
    )
  }

  return (
    <Box sx={{ height: "100%", overflow: "hidden" }} ref={containerRef}>
      <Box id={scrollableTargetId} sx={{ height: "100%", overflowY: "auto" }}>
        <InfiniteScroll
          dataLength={deployments.length}
          next={fetchNextPage}
          hasMore={hasNextPage ?? false}
          loader={deploymentLoader}
          scrollableTarget={scrollableTargetId}
          endMessage={!isPending ? deploymentEndMessage : null}
          style={{ overflow: "visible" }}
        >
          <List disablePadding>
            {deployments.map((deployment) => (
              <DeploymentItem
                key={deployment.id}
                deployment={deployment}
                showPipelineInfo={showPipelineInfo}
                onDeploymentClick={onDeploymentClick}
              />
            ))}
          </List>
        </InfiniteScroll>

        {/* Show loader when initially loading and no deployments yet */}
        {isPending && deployments.length === 0 && deploymentLoader}
      </Box>
    </Box>
  )
}
