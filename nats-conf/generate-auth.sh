#!/bin/bash

# This does the following:
# 1. Operator account, which acts as system account.
# 2. Operator account REQUIRES signing keys
# 3. APP account, account used for subjects we are publishing on (pipelines.>, etc.).
# We also enable jetstream, and generate a signing key for the account.
# 4. APP account user `backend_user`, used for backend services and includes jwt + nkey (in creds file).
# `backend_user` is signed with the account signing key.
# 5. AUTH account user `callout_user`, used for callout service to connect to NATS.
# 6. AUTH account user `frontend_user` -> this account is LOCKED DOWN (deny pubsub for all subjects).
# 7. AUTH account xkey for end-to-end encryption.

# The script generates the following artifacts to ./out:
# 1. auth.conf
# 2. callout_user.creds -> used on nats.connect() in the callout service
# 3. frontend_user.creds -> used on nats.connect() in the frontend 
# 4. backend_user.creds -> used on nats.connect() in the backend services
# 5. callout_account.nk -> used in callout service to sign JWTs. 
# NOTE/TODO: This isn't the root key. We get a mismatch error (shown in nats server debug mode) 
# that prevents authorization after token verification. If you are looking at this, this needs to be fixed.
# 6. app_account.nk -> unused?
# 7. callout_account_xkey.nk -> used for encryption in callout service

set -x

# put the nsc artifacts where we can find them
THIS_DIR=$(dirname $0)
export TMPDIR=/tmp
export OUTDIR=$TMPDIR/DA
export XDG_CONFIG_HOME=$OUTDIR/config
export XDG_DATA_HOME=$OUTDIR/data

rm -rf $OUTDIR

# add an operator
nsc add operator --name org --sys --generate-signing-key
nsc edit operator --require-signing-keys

## APP ACCOUNT
nsc add account APP 
nsc edit account APP --sk generate --js-enable 1
APP_ACCOUNT=$(nsc describe account APP --json | jq .sub -r) # public key
APP_ACCOUNT_SK=$(nsc describe account APP --json | jq -r '.nats.signing_keys[0]')
# Add backend services user and sign with the account signing key (not root key)
nsc add user backend_user --account APP -K $APP_ACCOUNT_SK
BACKEND_SERVICES_USER=$(nsc describe user backend_user --json | jq .sub -r) # public key


## AUTH CALLOUT ACCOUNT
nsc add account AUTH
nsc edit account AUTH --sk generate
# capture the ID (subject) for the callout account
CALLOUT_ACCOUNT=$(nsc describe account AUTH --json | jq .sub -r)
CALLOUT_ACCOUNT_SK=$(nsc describe account AUTH --json | jq -r '.nats.signing_keys[0]')
# add the service user, this user is for the callout service to connect to NATS
nsc add user callout_user --account AUTH -K $CALLOUT_ACCOUNT_SK
CALLOUT_USER=$(nsc describe user callout_user --json | jq .sub -r)
nsc add user frontend_user --deny-pubsub ">" --account AUTH -K $CALLOUT_ACCOUNT_SK
nsc edit authcallout --account AUTH --auth-user $CALLOUT_USER --auth-user $BACKEND_SERVICES_USER -x generate
CALLOUT_ACCOUNT_XKEY=$(nsc describe account AUTH --json | jq -r '.nats.authorization.xkey')
nsc list keys --all
nsc list keys --all -S

nsc describe user frontend_user
nsc describe user callout_user
nsc describe user backend_user -a APP

nsc generate config --mem-resolver --config-file $OUTDIR/auth.conf

nsc generate creds --account AUTH --name callout_user -o $OUTDIR/callout_user.creds
nsc generate creds --account AUTH --name frontend_user -o $OUTDIR/frontend_user.creds
nsc generate creds --account APP --name backend_user -o $OUTDIR/backend_user.creds

# copy the signing keys (not the root keys) to the output directory TODO: see todo above, we need to fix this.
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/A/${CALLOUT_ACCOUNT_SK:1:2}/${CALLOUT_ACCOUNT_SK}.nk" $OUTDIR/callout_account.nk
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/A/${APP_ACCOUNT_SK:1:2}/${APP_ACCOUNT_SK}.nk" $OUTDIR/app_account.nk
# copy the encryption key to the output directory
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/X/${CALLOUT_ACCOUNT_XKEY:1:2}/${CALLOUT_ACCOUNT_XKEY}.nk" $OUTDIR/callout_account_xkey.nk

mkdir -p $THIS_DIR/out
cp $OUTDIR/callout_account.nk $THIS_DIR/out/callout_account.nk
cp $OUTDIR/app_account.nk $THIS_DIR/out/app_account.nk
cp $OUTDIR/callout_user.creds $THIS_DIR/out/callout_user.creds
cp $OUTDIR/frontend_user.creds $THIS_DIR/out/frontend_user.creds
cp $OUTDIR/backend_user.creds $THIS_DIR/out/backend_user.creds
cp $OUTDIR/auth.conf $THIS_DIR/out/auth.conf
cp $OUTDIR/callout_account_xkey.nk $THIS_DIR/out/callout_account_xkey.nk