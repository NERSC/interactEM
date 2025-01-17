export interface OperatorInput {
  label: string;
  description: string;
}

export interface OperatorOutput {
  label: string;
  description: string;
}

export enum ParameterType {
  STRING = "str",
  INTEGER = "int",
  FLOAT = "float",
  BOOLEAN = "bool",
  MOUNT = "mount",
  STR_ENUM = "str-enum",
}

export interface OperatorParameter {
  name: string
  label: string
  description: string
  type: ParameterType
  default: string
  required: boolean
  value?: string
  options?: string[]
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

