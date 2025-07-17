# Model Descriptions

Pipelines are a DAG of Operators and Ports
We have to have some way of saying that

OperatorA -> OutputPortA -> InputPortB -> OperatorB

and

OperatorA -> OutputPortB -> InputPortC -> OperatorC

In other words, we cannot have a direct connection between
two operators because there needs to be some way of identifying
a specific output port of an operator to a specific input port of another operator
