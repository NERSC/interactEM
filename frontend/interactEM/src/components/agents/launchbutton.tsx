import { zodResolver } from "@hookform/resolvers/zod"
import { Add } from "@mui/icons-material"
import {
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import { useCallback, useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import {
  type AgentCreateEvent,
  agentsLaunchAgentMutation,
  zAgentCreateEvent,
} from "../../client"

// TODO: in the future, consider using: https://github.com/dohomi/react-hook-form-mui/
export const LaunchAgentButton = () => {
  const [open, setOpen] = useState(false)

  const launchAgent = useMutation({
    ...agentsLaunchAgentMutation(),
  })

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<AgentCreateEvent>({
    resolver: zodResolver(zAgentCreateEvent),
    defaultValues: {
      machine: "perlmutter",
      compute_type: "cpu",
      duration: "01:00:00",
      num_nodes: 1,
    },
  })
  const onSubmit: SubmitHandler<AgentCreateEvent> = useCallback(
    async (formData: AgentCreateEvent) => {
      try {
        launchAgent.mutate({
          body: formData,
        })
        setOpen(false)
      } catch (error) {
        console.error("Failed to launch agent:", error)
      }
    },
    [launchAgent],
  )

  return (
    <>
      <Chip
        icon={<Add />}
        label="Add agents"
        color="primary"
        variant="filled"
        clickable
        onClick={() => setOpen(true)}
        sx={{
          fontSize: "1rem",
          borderWidth: 2,
          borderColor: "primary.main",
          bgcolor: "primary.50",
          "&:hover": {
            bgcolor: "primary.100",
          },
        }}
        aria-label="Launch Agent"
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Launch Agent</DialogTitle>
        <DialogContent>
          <form id="launch-agent-form" onSubmit={handleSubmit(onSubmit)}>
            <FormControl
              fullWidth
              sx={{ marginTop: "1rem", marginBottom: "1rem" }}
            >
              <InputLabel error={!!errors.machine}>Machine</InputLabel>
              <Controller
                name="machine"
                control={control}
                render={({ field }) => (
                  <Select
                    {...field}
                    label="Machine"
                    variant="outlined"
                    error={!!errors.machine}
                    fullWidth
                  >
                    {zAgentCreateEvent.shape.machine._def.values.map(
                      (machine) => (
                        <MenuItem key={machine} value={machine}>
                          {machine}
                        </MenuItem>
                      ),
                    )}
                  </Select>
                )}
              />
            </FormControl>

            <FormControl fullWidth sx={{ marginBottom: "1rem" }}>
              <InputLabel error={!!errors.compute_type}>
                Compute Type
              </InputLabel>
              <Controller
                name="compute_type"
                control={control}
                render={({ field }) => (
                  <Select
                    {...field}
                    label="Compute Type"
                    variant="outlined"
                    error={!!errors.compute_type}
                    fullWidth
                  >
                    {zAgentCreateEvent.shape.compute_type._def.values.map(
                      (compute_type) => (
                        <MenuItem key={compute_type} value={compute_type}>
                          {compute_type}
                        </MenuItem>
                      ),
                    )}
                  </Select>
                )}
              />
            </FormControl>

            <FormControl fullWidth sx={{ marginBottom: "1rem" }}>
              <Controller
                name="duration"
                control={control}
                render={({ field }) => (
                  <TextField
                    label="Duration (HH:MM:SS)"
                    variant="outlined"
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    value={field.value}
                    fullWidth
                    error={!!errors.duration}
                    helperText={errors.duration?.message}
                  />
                )}
              />
            </FormControl>

            <FormControl fullWidth sx={{ marginBottom: "1rem" }}>
              <Controller
                name="num_nodes"
                control={control}
                render={({ field }) => (
                  <TextField
                    label="Number of Nodes"
                    variant="outlined"
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    value={field.value}
                    fullWidth
                    error={!!errors.num_nodes}
                    helperText={
                      errors.num_nodes ? "This should be an integer." : ""
                    }
                  />
                )}
              />
            </FormControl>
          </form>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            type="submit"
            form="launch-agent-form"
            color="primary"
            disabled={launchAgent.isPending}
          >
            {launchAgent.isPending ? "Launching..." : "Launch"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
