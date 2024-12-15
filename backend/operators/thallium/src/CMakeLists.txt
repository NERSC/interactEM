# Bindings

# Create the extension module
nanobind_add_module(
  # Name of the extension
  _thallium

  # Target the stable ABI for Python 3.12+, which reduces
  # the number of binary wheels that must be built. This
  # does nothing on older Python versions
  STABLE_ABI

  # Build libnanobind statically and merge it into the
  # extension (which itself remains a shared library)
  #
  # If your project builds multiple extensions, you can
  # replace this flag by NB_SHARED to conserve space by
  # reusing a shared libnanobind across libraries
  NB_STATIC

  # Source code goes here
  bindings.cpp
  QueueProvider.hpp
  QueueClient.hpp
  proto/message.capnp.c++
)

# Make a dep for generated schemas
add_dependencies(_thallium ${THALLIUM_FBS_SCHEMAS_TARGET})

target_link_libraries(_thallium PRIVATE thallium CapnProto::capnp)

# Figured this out, and then found this discussion as a good ref:
# https://github.com/wjakob/nanobind/discussions/537
nanobind_add_stub(
    thallium_stub
    MODULE _thallium
    OUTPUT __init__.pyi
    MARKER_FILE py.typed
    PYTHON_PATH $<TARGET_FILE_DIR:_thallium>
    DEPENDS _thallium
)


# Install directive for scikit-build-core
install(TARGETS _thallium LIBRARY DESTINATION thallium)
install(FILES
  ${CMAKE_BINARY_DIR}/src/py.typed
  ${CMAKE_BINARY_DIR}/src/__init__.pyi
  DESTINATION thallium
)