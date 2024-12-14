# Generate CapnProto
set(CAPNP_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
execute_process(
  COMMAND capnp compile -oc++ "${CAPNP_DIR}/message.capnp"
  WORKING_DIRECTORY "${CAPNP_DIR}"
  RESULT_VARIABLE CAPNP_RESULT
)
if(CAPNP_RESULT EQUAL 0)
    message(STATUS "Cap'n Proto compilation succeeded.")
else()
    message(ERROR "Cap'n Proto compilation failed.")
endif()