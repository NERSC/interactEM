import { useMutation } from "@tanstack/react-query"
import { pipelinesRunPipelineMutation } from "../client"

export const useRunPipeline = () => {
  return useMutation({
    ...pipelinesRunPipelineMutation(),
    onError: (error) => {
      console.error("Error running pipeline:", error)
    },
    onSuccess: (data) => {
      console.log("Pipeline launched:", data)
    },
    onSettled: () => {
      console.log("Pipeline launch settled.")
    },
  })
}
