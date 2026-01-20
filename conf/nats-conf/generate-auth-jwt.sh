#!/bin/bash

# put the nsc artifacts where we can find them
THIS_DIR=$(dirname $0)
AUTH_CONF_FILENAME=auth.conf
AUTH_CONF_PATH="${THIS_DIR}/out_jwt/${AUTH_CONF_FILENAME}"
FRONTEND_CREDS_PATH="${THIS_DIR}/out_jwt/frontend.creds"

if [ -f "$AUTH_CONF_PATH" ]; then
    if grep -q "^default_sentinel:" "$AUTH_CONF_PATH"; then
        echo "NATS configuration already exists with default_sentinel, skipping generation"
        exit 0
    fi
    if [ -f "$FRONTEND_CREDS_PATH" ]; then
        DEFAULT_SENTINEL_JWT=$(sed -n '2p' "$FRONTEND_CREDS_PATH")
        if [ -n "$DEFAULT_SENTINEL_JWT" ]; then
            printf '\ndefault_sentinel: "%s"\n' "$DEFAULT_SENTINEL_JWT" >> "$AUTH_CONF_PATH"
            echo "Added default_sentinel to existing auth.conf"
            exit 0
        fi
    fi
    echo "auth.conf exists without default_sentinel, regenerating"
fi

mkdir -p "$THIS_DIR/out_jwt"
exec > >(tee -i ${THIS_DIR}/out_jwt/output.log) 2>&1
export NSC_WORK_DIR="/tmp/interactem-nsc-auth"
export XDG_CONFIG_HOME="${NSC_WORK_DIR}/config"
export XDG_DATA_HOME="${NSC_WORK_DIR}/data"

rm -rf "$NSC_WORK_DIR"
mkdir -p "$NSC_WORK_DIR"

echo "---------------------"
echo "Setting up NATS AuthN"
echo "---------------------"

# add an operator
ORG_NAME=org
nsc add operator --name $ORG_NAME --sys --generate-signing-key
nsc edit operator --require-signing-keys
ORG_ACCOUNT=$(nsc describe operator $ORG_NAME --json | jq .sub -r)
ORG_ACCOUNT_SK=$(nsc describe operator $ORG_NAME --json | jq -r '.nats.signing_keys[0]')

## SYS ACCOUNT
SYS_ACCOUNT_NAME=SYS
SYS_ACCOUNT=$(nsc describe account $SYS_ACCOUNT_NAME --json | jq .sub -r)
SYS_ACCOUNT_SK=$(nsc describe account $SYS_ACCOUNT_NAME --json | jq -r '.nats.signing_keys[0]')
SYS_USER_NAME=sys

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
nsc generate config --mem-resolver --config-file $NSC_WORK_DIR/$AUTH_CONF_FILENAME

# Generate credentials for all of the users
nsc generate creds --account $CALLOUT_ACCOUNT_NAME --name $CALLOUT_USER_NAME -o $NSC_WORK_DIR/$CALLOUT_USER_NAME.creds
nsc generate creds --account $CALLOUT_ACCOUNT_NAME --name $FRONTEND_USER_NAME -o $NSC_WORK_DIR/$FRONTEND_USER_NAME.creds
nsc generate creds --account $APP_ACCOUNT_NAME --name $BACKEND_USER_NAME -o $NSC_WORK_DIR/$BACKEND_USER_NAME.creds
nsc generate creds --account $APP_ACCOUNT_NAME --name $OPERATOR_USER_NAME -o $NSC_WORK_DIR/$OPERATOR_USER_NAME.creds
nsc generate creds --account $SYS_ACCOUNT_NAME --name $SYS_USER_NAME -o $NSC_WORK_DIR/$SYS_USER_NAME.creds

# Use the bearer frontend JWT as the default sentinel so clients can omit creds.
DEFAULT_SENTINEL_JWT=$(sed -n '2p' "$NSC_WORK_DIR/$FRONTEND_USER_NAME.creds")
printf '\ndefault_sentinel: "%s"\n' "$DEFAULT_SENTINEL_JWT" >> "$NSC_WORK_DIR/$AUTH_CONF_FILENAME"

mkdir -p $THIS_DIR/out_jwt
CP_DIR=$THIS_DIR/out_jwt
cp "$NSC_WORK_DIR"/*.creds "$CP_DIR"/
cp "$NSC_WORK_DIR/$AUTH_CONF_FILENAME" "$CP_DIR/$AUTH_CONF_FILENAME"

rm -rf "$CP_DIR/raw_output"
mkdir -p "$CP_DIR/raw_output"
cp "$NSC_WORK_DIR/$AUTH_CONF_FILENAME" "$CP_DIR/raw_output/$AUTH_CONF_FILENAME"
cp -R "$NSC_WORK_DIR/data" "$CP_DIR/raw_output/data"
cp -R "$NSC_WORK_DIR/config" "$CP_DIR/raw_output/config"

# Create a tarball of raw_output and base64 encode it (for kubectl/helm)
rm -f $CP_DIR/raw_output.tar.gz
tar -czf $CP_DIR/raw_output.tar.gz -C $CP_DIR/raw_output .
if base64 --help 2>&1 | grep -q -- "-w"; then
    base64 -w 0 "$CP_DIR/raw_output.tar.gz" > "$CP_DIR/raw_output.tar.gz.b64"
else
    base64 -i "$CP_DIR/raw_output.tar.gz" -o "$CP_DIR/raw_output.tar.gz.b64"
fi

# Printout all the information
echo -e "\n\n\n\n"
echo "---------------"
echo "Raw output tree"
echo "---------------"
tree "$CP_DIR/raw_output"

echo -e "\n\n\n\n"
echo "--------"
echo "OPERATOR"
echo "--------"
nsc describe operator $ORG_NAME

# SYS account
echo -e "\n\n\n\n"
echo "---"
echo "SYS"
echo "---"
nsc describe account $SYS_ACCOUNT_NAME

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
nsc describe user $CALLOUT_USER_NAME


echo -e "\n\n\n\n"
echo "----"
echo "KEYS"
echo "----"
nsc list keys --all
nsc list keys --all -S
