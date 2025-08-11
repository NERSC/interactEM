# RDMA Proxy core library
add_library(rdma_proxy_core SHARED
    # RdmaProxyService.cpp
    # op_receiver.cpp
    # op_sender.cpp
    prx_transporter.cpp
)

# Include directories for the core library
target_include_directories(rdma_proxy_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../common/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../libs/thallium/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../libs/argobots/include
)

# Link dependencies
target_link_libraries(rdma_proxy_core PUBLIC
    common_utils
    rdma_external_libs
    thallium
)

# Set compile features
target_compile_features(rdma_proxy_core PUBLIC cxx_std_17)
