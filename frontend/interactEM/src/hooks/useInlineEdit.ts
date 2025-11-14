import { useState } from "react"

interface UseInlineEditOptions {
  initialValue: string
  onSave: (newValue: string) => void
  onEditingChange: (isEditing: boolean) => void
}

interface UseInlineEditReturn {
  value: string
  handleEditClick: (e: React.MouseEvent) => void
  handleCancelClick: (e: React.MouseEvent) => void
  handleValueChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  handleKeyDown: (e: React.KeyboardEvent) => void
}

export const useInlineEdit = ({
  initialValue,
  onSave,
  onEditingChange,
}: UseInlineEditOptions): UseInlineEditReturn => {
  const [value, setValue] = useState(initialValue)

  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onEditingChange(true)
  }

  const handleCancelClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setValue(initialValue)
    onEditingChange(false)
  }

  const handleValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      onSave(value)
    } else if (e.key === "Escape") {
      setValue(initialValue)
      onEditingChange(false)
    }
  }

  return {
    value,
    handleEditClick,
    handleCancelClick,
    handleValueChange,
    handleKeyDown,
  }
}
