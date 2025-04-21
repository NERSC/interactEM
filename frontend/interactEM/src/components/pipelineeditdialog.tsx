import {
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material"
import type React from "react"
import { useEffect, useState } from "react"

interface PipelineEditDialogProps {
  open: boolean
  onClose: () => void
  onSave: (newName: string) => void
  initialName: string
  isSaving: boolean
}

export const PipelineEditDialog: React.FC<PipelineEditDialogProps> = ({
  open,
  onClose,
  onSave,
  initialName,
  isSaving,
}) => {
  const [name, setName] = useState(initialName)

  useEffect(() => {
    if (open) {
      setName(initialName)
    }
  }, [open, initialName])

  const handleSave = () => {
    onSave(name)
  }

  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setName(event.target.value)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Edit Pipeline Name</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin="dense"
          id="name"
          label="Pipeline Name"
          type="text"
          fullWidth
          variant="outlined"
          value={name}
          onChange={handleNameChange}
          disabled={isSaving}
          onKeyDown={(e) => e.key === "Enter" && !isSaving && handleSave()}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={isSaving} variant="contained">
          {isSaving ? <CircularProgress size={24} /> : "Save"}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
