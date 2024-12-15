# Generate CapnProto
set(CAPNP_PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
execute_process(
  COMMAND capnp compile -oc++ "${CAPNP_PROTO_DIR}/message.capnp"
  WORKING_DIRECTORY "${CAPNP_PROTO_DIR}"
  RESULT_VARIABLE CAPNP_COMPILE_RESULT
)
if(CAPNP_COMPILE_RESULT EQUAL 0)
    message(STATUS "Cap'n Proto compilation succeeded.")
else()
    message(ERROR "Cap'n Proto compilation failed.")
endif()

# Generate FlatBuffers
# See this project for an example:
# https://github.com/ogmacorp/OgmaNeo/blob/3edd6b3e9ff044ab7a924d1871c92b8762390379/CMakeLists.txt#L154
set(THALLIUM_FBS_PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
set(THALLIUM_FBS_SCHEMAS 
    "${THALLIUM_FBS_PROTO_DIR}/message.fbs"
)

# Cache target name so we can add it as a dependency later
set(THALLIUM_FBS_SCHEMAS_TARGET "thallium_schemas" CACHE STRING "Target for FlatBuffers schemas")

build_flatbuffers(
    "${THALLIUM_FBS_SCHEMAS}" 
    "${THALLIUM_FBS_PROTO_DIR}" 
    "${THALLIUM_FBS_SCHEMAS_TARGET}" 
    ""                          # No additional_dependencies
    "${THALLIUM_FBS_PROTO_DIR}"  # Where to generate include files
    ""                          # No binary schemas directory
    ""                          # No copy text schemas
)

set_property(TARGET ${THALLIUM_FBS_SCHEMAS_TARGET} APPEND PROPERTY SOURCES ${THALLIUM_FBS_SCHEMAS})