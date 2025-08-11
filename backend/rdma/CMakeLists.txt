
cmake_minimum_required(VERSION 3.15...3.26)

project(thallium-mochi-rdma VERSION 0.1.0 LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(thallium REQUIRED)
find_package(PkgConfig REQUIRED)

add_subdirectory(common)
add_subdirectory(libs)
add_subdirectory(src)

# Main executable
# add_executable(rdma_proxy main.cpp bindings.cpp)
add_executable(rdma_proxy main.cpp)

# Include directories for main executable
target_include_directories(rdma_proxy PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/common/include
    ${CMAKE_CURRENT_SOURCE_DIR}/libs/thallium/include
    ${CMAKE_CURRENT_SOURCE_DIR}/libs/argobots/include
)

# Link libraries to main executable
target_link_libraries(rdma_proxy PRIVATE
    rdma_proxy_core 
    rdma_external_libs 
    thallium 
)