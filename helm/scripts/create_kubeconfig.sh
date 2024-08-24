#!/bin/bash

kubectl -n interactem create secret generic kubeconfig --from-file=kubeconfig=${HOME}/.kube/config
