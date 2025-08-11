/**
 * @file proto_type.hpp
 * @brief Defines supported network protocol types and conversion utilities
 * 
 * Enumerates various network protocols (TCP, UDP, CXI, VERBS, etc.) supported
 * by the RDMA proxy and provides string conversion utilities for protocol handling.
 */

#pragma once

#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>

namespace interactEM {

enum class ProtocolType {
    TCP,
    UDP,
    SOCKETS,
    CXI,
    VERBS,
    UNKNOWN
};

// Convert ProtocolType to string
inline std::string to_string(ProtocolType type) {
    static const std::unordered_map<ProtocolType, std::string> type_map = {
        {ProtocolType::TCP, "ofi+tcp"},
        {ProtocolType::UDP, "ofi+udp"},
        {ProtocolType::SOCKETS, "ofi+sockets"},
        {ProtocolType::CXI, "ofi+cxi"},
        {ProtocolType::VERBS, "ofi+verbs"},
        {ProtocolType::UNKNOWN, "Unknown"}
    };
    
    auto it = type_map.find(type);
    return (it != type_map.end()) ? it->second : "Invalid";
}

// Convert string to ProtocolType
inline ProtocolType from_string(const std::string& str) {
    static const std::unordered_map<std::string, ProtocolType> string_map = {
        {"ofi+tcp", ProtocolType::TCP},
        {"ofi+udp", ProtocolType::UDP},
        {"ofi+sockets", ProtocolType::SOCKETS},
        {"ofi+cxi", ProtocolType::CXI},
        {"ofi+verbs", ProtocolType::VERBS},
        {"Unknown", ProtocolType::UNKNOWN},
    };
    
    auto it = string_map.find(str);
    if (it != string_map.end()) {
        return it->second;
    }
    throw std::invalid_argument("Invalid protocol type string: " + str);
}

inline std::ostream& operator<<(std::ostream& os, ProtocolType type) {
    return os << to_string(type);
}

}

