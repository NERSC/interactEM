import { useMutation } from "@tanstack/react-query"
import { runPipelineMutation } from "../client"

export const useRunPipeline = () => {
  return useMutation({
    ...runPipelineMutation(),
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
