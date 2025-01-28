# Build stage with Spack pre-installed and ready to be used
FROM spack/ubuntu-jammy:develop as builder

# What we want to install and how we want to install it
# is specified in a manifest file (spack.yaml)
RUN mkdir -p /opt/spack-environment && \
    set -o noclobber \
    &&  (echo spack: \
    &&   echo '  specs:' \
    &&   echo '  - cmake' \
    &&   echo '  - pkgconfig' \
    &&   echo '  - mochi-thallium ^mercury~boostsys~checksum ^libfabric fabrics=tcp,rxm' \
    &&   echo '  - nlohmann-json' \
    &&   echo '  - spdlog' \
    &&   echo '  - fmt' \
    &&   echo '  - tclap' \
    &&   echo '  - flatbuffers' \
    &&   echo '  concretizer:' \
    &&   echo '    unify: true' \
    &&   echo '    reuse: true' \
    &&   echo '  packages:' \
    &&   echo '    mochi-margo:' \
    &&   echo '      require: '"'"'@0.18.3:'"'"'' \
    &&   echo '    mochi-thallium:' \
    &&   echo '      require: '"'"'@0.14.6:'"'"'' \
    &&   echo '  config:' \
    &&   echo '    install_tree: /opt/software' \
    &&   echo '  view: /opt/views/view') > /opt/spack-environment/spack.yaml

# Install the software, remove unnecessary deps
RUN cd /opt/spack-environment && spack env activate . && spack install --fail-fast && spack gc -y

# Strip all the binaries
RUN find -L /opt/views/view/* -type f -exec readlink -f '{}' \; | \
    xargs file -i | \
    grep 'charset=binary' | \
    grep 'x-executable\|x-archive\|x-sharedlib' | \
    awk -F: '{print $1}' | xargs strip

# Modifications to the environment that are necessary to run
RUN cd /opt/spack-environment && \
    spack env activate --sh -d . > activate.sh


# Bare OS image to run the installed executables
FROM interactem/operator

RUN apt-get update && apt-get install -y \
    git gcc automake pkgconf \
    python3-pip && rm -rf /var/lib/apt/lists/*

RUN pip install \
    nanobind

COPY --from=builder /opt/spack-environment /opt/spack-environment
COPY --from=builder /opt/software /opt/software

# paths.view is a symlink, so copy the parent to avoid dereferencing and duplicating it
COPY --from=builder /opt/views /opt/views

RUN { \
    echo '#!/bin/sh' \
    && echo '.' /opt/spack-environment/activate.sh \
    && echo 'exec "$@"'; \
    } > /entrypoint.sh \
    && chmod a+x /entrypoint.sh \
    && ln -s /opt/views/view /opt/view


ENTRYPOINT [ "/entrypoint.sh" ]
CMD [ "/bin/bash" ]

