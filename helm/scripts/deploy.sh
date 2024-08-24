#!/bin/bash

export SPIN_GID=99894
export SPIN_UID=99894

cd ../spin-helm/nats/kustomize

helm upgrade --install -n interactem nats nats/nats --version 1.2.2 -f ../../../nats-values.yaml --post-renderer ./kustomize.sh

cd ../../..
helm upgrade --install -n interactem -f ./tls-acme-values.yaml acmecron ./spin-helm/tls-acme