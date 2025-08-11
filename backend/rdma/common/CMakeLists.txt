# Common utilities library (header-only for now)
add_library(common_utils INTERFACE)

# Include directories for common utilities
target_include_directories(common_utils INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(common_utils INTERFACE cxx_std_17)
