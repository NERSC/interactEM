# Argobots utility library
add_library(argobots_utils SHARED
    src/abt_manager.cpp
    # src/abt_pool.cpp
    # src/abt_scheduler.cpp
)

# Include directories for Argobots utility library
target_include_directories(argobots_utils PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../../common/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../argobots/include
)

# Link external thallium dependency
target_link_libraries(argobots_utils PUBLIC
    thallium
)

target_compile_features(argobots_utils PUBLIC cxx_std_17)
