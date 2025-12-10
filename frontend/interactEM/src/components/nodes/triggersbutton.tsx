import FlashOnIcon from "@mui/icons-material/FlashOn"
import { Box, Button, Paper, Stack, Typography } from "@mui/material"
import type { ButtonProps } from "@mui/material/Button"
import type React from "react"
import { toast } from "react-toastify"

import { useTriggerInvoke } from "../../hooks/nats/useTriggerInvoke"
import type { OperatorSpecTrigger } from "../../types/triggers"
import NodeModalButton from "./nodemodalbutton"

const TriggerCard: React.FC<{
  operatorID: string
  trigger: OperatorSpecTrigger
  disabled: boolean
}> = ({ operatorID, trigger, disabled }) => {
  const { mutateAsync, isPending, isError, isSuccess } =
    useTriggerInvoke(operatorID)

  const buttonColor: ButtonProps["color"] = isError
    ? "error"
    : isSuccess
      ? "success"
      : "warning"

  const handleTrigger = async () => {
    try {
      await mutateAsync({ trigger })
      toast.success(`Triggered "${trigger.label}"`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Trigger failed")
    }
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Stack spacing={1.5}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="start"
          spacing={2}
        >
          <Box>
            <Typography variant="subtitle2" fontWeight={700}>
              {trigger.label}
            </Typography>
          </Box>
          <Button
            variant="contained"
            color={buttonColor}
            size="small"
            startIcon={<FlashOnIcon />}
            onClick={handleTrigger}
            disabled={disabled || isPending}
          >
            Trigger
          </Button>
        </Stack>

        {trigger.description && (
          <Typography variant="caption" color="text.secondary">
            {trigger.description}
          </Typography>
        )}
      </Stack>
    </Paper>
  )
}

const TriggersButton: React.FC<{
  operatorID: string
  triggers: OperatorSpecTrigger[]
  nodeRef: React.RefObject<HTMLDivElement>
  disabled?: boolean
}> = ({ operatorID, triggers, nodeRef, disabled = false }) => {
  return (
    <NodeModalButton
      nodeRef={nodeRef}
      icon={<FlashOnIcon fontSize="small" />}
      label="Triggers"
      title={null}
      disabled={disabled}
      minWidth={340}
    >
      {triggers.length > 0 ? (
        <Stack spacing={1.5}>
          {triggers.map((trigger) => (
            <TriggerCard
              key={trigger.name}
              operatorID={operatorID}
              trigger={trigger}
              disabled={disabled}
            />
          ))}
        </Stack>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No triggers available.
        </Typography>
      )}
    </NodeModalButton>
  )
}

export default TriggersButton
