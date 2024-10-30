import operatorsJSON from "./operators.json"

export interface OperatorInput {
  label: string
  description: string
}

export interface OperatorOutput {
  label: string
  description: string
}

export interface OperatorParameter {
  name: string
  label: string
  description: string
  type: string
  default: string
  required: boolean
}

export interface Operator {
  id: string
  label: string
  description: string
  image: string
  inputs?: OperatorInput[]
  outputs?: OperatorOutput[]
  parameters?: OperatorParameter[]
}

export const operators = () => operatorsJSON as Operator[]

export const operatorByID = (id: string) =>
  operators().find((op) => op.id === id)
