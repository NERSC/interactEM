#!/bin/bash

# This is a "dumbed down" version of the jwt script. 
# We are only generating nkeys here, no need to worry about JWT/signing, etc.
# We use this mode now, and if we can figure out getting frontend jwt to work,
# we can switch.

# set -x

# put the nsc artifacts where we can find them
THIS_DIR=$(dirname $0)
export OUTDIR=$THIS_DIR/out_nkey

rm -rf $OUTDIR
mkdir -p $OUTDIR

# Generate the seed and public key pair
nk -gen user > $OUTDIR/auth_user.nk
nk -gen user > $OUTDIR/app_user.nk
nk -gen account > $OUTDIR/auth_issuer.nk
nk -gen curve > $OUTDIR/auth_xkey.nk

# Extract the public key from the generated seed
export AUTH_USER_NKEY=$(nk -inkey $OUTDIR/auth_user.nk -pubout)
export APP_USER_NKEY=$(nk -inkey $OUTDIR/app_user.nk -pubout)
export AUTH_CALL_OUT_ISSUER=$(nk -inkey $OUTDIR/auth_issuer.nk -pubout)
export AUTH_CALL_OUT_XKEY=$(nk -inkey $OUTDIR/auth_xkey.nk -pubout)

# Create the config file
cat <<EOF > $OUTDIR/auth.conf
accounts {
  AUTH: {
    users: [ { nkey: $AUTH_USER_NKEY }]
  }
  APP: {
    jetstream: enable
    users: [ { nkey: $APP_USER_NKEY }]
  }
  SYS: {}
}
system_account: SYS

authorization {
  auth_callout {
    issuer: $AUTH_CALL_OUT_ISSUER
    auth_users: [ $AUTH_USER_NKEY, $APP_USER_NKEY ]
    account: AUTH
    xkey: $AUTH_CALL_OUT_XKEY
  }
}
EOF

# Output the public key for user reference
echo "Configuration file 'auth.conf' generated successfully."