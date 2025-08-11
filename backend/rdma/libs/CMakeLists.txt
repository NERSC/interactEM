
add_subdirectory(thallium)
add_subdirectory(argobots)

# Create a meta-library that aggregates all external library dependencies
add_library(rdma_external_libs INTERFACE)

# Link all external library wrappers to the meta-library
target_link_libraries(rdma_external_libs INTERFACE
    thallium_engine
    argobots_utils  
)

# Export include directories for consumers
target_include_directories(rdma_external_libs INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/thallium/include
    ${CMAKE_CURRENT_SOURCE_DIR}/argobots/include
)

target_compile_features(rdma_external_libs INTERFACE cxx_std_17)