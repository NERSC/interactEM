#!/bin/bash

# put the nsc artifacts where we can find them
THIS_DIR=$(dirname $0)
export TMPDIR=/tmp
export OUTDIR=$TMPDIR/DA
export XDG_CONFIG_HOME=$OUTDIR/config
export XDG_DATA_HOME=$OUTDIR/data

rm -rf $OUTDIR

# add an operator
ORG_NAME=org
nsc add operator --name $ORG_NAME --sys --generate-signing-key
nsc edit operator --require-signing-keys

## APP ACCOUNT
APP_ACCOUNT_NAME=APP
nsc add account $APP_ACCOUNT_NAME 
nsc edit account $APP_ACCOUNT_NAME --sk generate --js-enable 1
APP_ACCOUNT=$(nsc describe account $APP_ACCOUNT_NAME --json | jq .sub -r) # public key
APP_ACCOUNT_SK=$(nsc describe account $APP_ACCOUNT_NAME --json | jq -r '.nats.signing_keys[0]')

# Add backend user and sign with the APP account signing key (not root key)
BACKEND_USER_NAME=backend
nsc add user $BACKEND_USER_NAME --account $APP_ACCOUNT_NAME -K $APP_ACCOUNT_SK
BACKEND_USER=$(nsc describe user $BACKEND_USER_NAME --json | jq .sub -r) # public key

# Add operator user and sign with the APP account signing key
OPERATOR_USER_NAME=operator
nsc add user $OPERATOR_USER_NAME --account $APP_ACCOUNT_NAME -K $APP_ACCOUNT_SK
OPERATOR_USER=$(nsc describe user $OPERATOR_USER_NAME --json | jq .sub -r) # public key

## AUTH CALLOUT ACCOUNT
CALLOUT_ACCOUNT_NAME=CALLOUT
nsc add account $CALLOUT_ACCOUNT_NAME
nsc edit account $CALLOUT_ACCOUNT_NAME --sk generate
CALLOUT_ACCOUNT=$(nsc describe account $CALLOUT_ACCOUNT_NAME --json | jq .sub -r)
CALLOUT_ACCOUNT_SK=$(nsc describe account $CALLOUT_ACCOUNT_NAME --json | jq -r '.nats.signing_keys[0]')

# add the callout user, this user is for the callout service to connect to NATS
CALLOUT_USER_NAME=callout
nsc add user $CALLOUT_USER_NAME --account $CALLOUT_ACCOUNT_NAME -K $CALLOUT_ACCOUNT_SK
CALLOUT_USER=$(nsc describe user $CALLOUT_USER_NAME --json | jq .sub -r)

# Add frontend user (like sentinel in the callout.go delegated auth example)
# This user is locked down, only to act as a frontend
FRONTEND_USER_NAME=frontend 
nsc add user $FRONTEND_USER_NAME --deny-pubsub ">" --bearer --account $CALLOUT_ACCOUNT_NAME -K $CALLOUT_ACCOUNT_SK
nsc edit authcallout --account $CALLOUT_ACCOUNT_NAME --allowed-account $APP_ACCOUNT --auth-user $CALLOUT_USER --auth-user $BACKEND_USER -x generate
CALLOUT_ACCOUNT_XKEY=$(nsc describe account $CALLOUT_ACCOUNT_NAME --json | jq -r '.nats.authorization.xkey')

# Generate configuration file
AUTH_CONF_FILENAME=auth.conf
nsc generate config --mem-resolver --config-file $OUTDIR/$AUTH_CONF_FILENAME

# Generate credentials for all of the users
nsc generate creds --account $CALLOUT_ACCOUNT_NAME --name $CALLOUT_USER_NAME -o $OUTDIR/$CALLOUT_USER_NAME.creds
nsc generate creds --account $CALLOUT_ACCOUNT_NAME --name $FRONTEND_USER_NAME -o $OUTDIR/$FRONTEND_USER_NAME.creds
nsc generate creds --account $APP_ACCOUNT_NAME --name $BACKEND_USER_NAME -o $OUTDIR/$BACKEND_USER_NAME.creds
nsc generate creds --account $APP_ACCOUNT_NAME --name $OPERATOR_USER_NAME -o $OUTDIR/$OPERATOR_USER_NAME.creds

# copy the signing keys (not the root keys) to the output directory TODO: see todo above, we need to fix this.
CALLOUT_ACCOUNT_FILE=${CALLOUT_ACCOUNT_NAME}.nk
CALLOUT_ACCOUNT_SK_FILE=${CALLOUT_ACCOUNT_NAME}_sk.nk
CALLOUT_ACCOUNT_XKEY_FILE=${CALLOUT_ACCOUNT_NAME}_xkey.nk
APP_ACCOUNT_FILE=${APP_ACCOUNT_NAME}.nk
APP_ACCOUNT_SK_FILE=${APP_ACCOUNT_NAME}_sk.nk

cp "$XDG_DATA_HOME/nats/nsc/keys/keys/A/${CALLOUT_ACCOUNT:1:2}/${CALLOUT_ACCOUNT}.nk" $OUTDIR/$CALLOUT_ACCOUNT_SK_FILE
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/A/${CALLOUT_ACCOUNT_SK:1:2}/${CALLOUT_ACCOUNT_SK}.nk" $OUTDIR/$CALLOUT_ACCOUNT_FILE
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/X/${CALLOUT_ACCOUNT_XKEY:1:2}/${CALLOUT_ACCOUNT_XKEY}.nk" $OUTDIR/$CALLOUT_ACCOUNT_XKEY_FILE
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/A/${APP_ACCOUNT:1:2}/${APP_ACCOUNT}.nk" $OUTDIR/$APP_ACCOUNT_FILE
cp "$XDG_DATA_HOME/nats/nsc/keys/keys/A/${APP_ACCOUNT_SK:1:2}/${APP_ACCOUNT_SK}.nk" $OUTDIR/$APP_ACCOUNT_SK_FILE

mkdir -p $THIS_DIR/out_jwt
CP_DIR=$THIS_DIR/out_jwt
cp $OUTDIR/$CALLOUT_ACCOUNT_FILE $CP_DIR/$CALLOUT_ACCOUNT_FILE
cp $OUTDIR/$CALLOUT_ACCOUNT_SK_FILE $CP_DIR/$CALLOUT_ACCOUNT_SK_FILE
cp $OUTDIR/$APP_ACCOUNT_FILE $CP_DIR/$APP_ACCOUNT_FILE
cp $OUTDIR/$CALLOUT_USER_NAME.creds $CP_DIR/$CALLOUT_USER_NAME.creds
cp $OUTDIR/$FRONTEND_USER_NAME.creds $CP_DIR/$FRONTEND_USER_NAME.creds
cp $OUTDIR/$BACKEND_USER_NAME.creds $CP_DIR/$BACKEND_USER_NAME.creds
cp $OUTDIR/$OPERATOR_USER_NAME.creds $CP_DIR/$OPERATOR_USER_NAME.creds
cp $OUTDIR/$AUTH_CONF_FILENAME $CP_DIR/$AUTH_CONF_FILENAME
cp $OUTDIR/$CALLOUT_ACCOUNT_XKEY_FILE $CP_DIR/$CALLOUT_ACCOUNT_XKEY_FILE
cp $OUTDIR/$APP_ACCOUNT_SK_FILE $CP_DIR/$APP_ACCOUNT_SK_FILE

# Printout all the information
echo -e "\n\n\n\n"
echo "--------"
echo "OPERATOR"
echo "--------"
nsc describe operator $ORG_NAME

# APP account + its users
echo -e "\n\n\n\n"
echo "---"
echo "APP"
echo "---"

nsc describe account $APP_ACCOUNT_NAME 
nsc describe user $BACKEND_USER_NAME -a $APP_ACCOUNT_NAME
nsc describe user $OPERATOR_USER_NAME -a $APP_ACCOUNT_NAME

# CALLOUT account + its users
echo -e "\n\n\n\n"
echo "-------"
echo "CALLOUT"
echo "-------"
nsc describe account $CALLOUT_ACCOUNT_NAME
nsc describe user $FRONTEND_USER_NAME
nsc describe user $CALLOUT_USER_NAME


echo -e "\n\n\n\n"
echo "----"
echo "KEYS"
echo "----"
nsc list keys --all
nsc list keys --all -S