
/**
 * @file op_mode.hpp
 * @brief Defines operation modes for RDMA proxy service
 * 
 * Contains enumeration for different operation modes (SERVER, CLIENT, UNKNOWN)
 * using Thallium constants to determine the proxy's operational behavior.
 */

#pragma once

#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <thallium.hpp>

namespace interactEM {

enum class OperationMode {
    SERVER = THALLIUM_SERVER_MODE,
    CLIENT = THALLIUM_CLIENT_MODE
};

}


