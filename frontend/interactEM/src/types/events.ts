export enum OperatorEventType {
  RUNNING = "running",
  STOPPED = "stopped",
  ERROR = "error",
}

export interface OperatorEvent {
  type: OperatorEventType
  operator_id: string
}

export type OperatorErrorType = "processing"

export interface OperatorErrorEvent extends OperatorEvent {
  type: OperatorEventType.ERROR
  error_type: OperatorErrorType
  message: string
}
