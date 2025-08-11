# Fetch the nlohmann_json library
include(FetchContent)
FetchContent_Declare(
  json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.11.2 # specify a version tag
)
FetchContent_MakeAvailable(json)

# Thallium engine library
add_library(thallium_engine SHARED
    src/eng_utils.cpp
    src/eng_provider.cpp
    # src/eng_dispatcher.cpp
    src/eng_registry.cpp
)

# Include directories for thallium library
target_include_directories(thallium_engine PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../../common/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../argobots/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../thallium/include
)

# Link external thallium dependency
target_link_libraries(thallium_engine PUBLIC
    thallium
    nlohmann_json::nlohmann_json
)

target_compile_features(thallium_engine PUBLIC cxx_std_17)
