export type OperatorEventType = "running" | "stopped" | "error"

export interface OperatorEvent {
  type: OperatorEventType
  operator_id: string
}

export type OperatorErrorType = "processing"

export interface OperatorErrorEvent extends OperatorEvent {
  type: "error"
  error_type: OperatorErrorType
  message: string
}
