
#pragma once

#include <string>
#include <optional>
#include <nlohmann/json.hpp>

namespace interactEM {
namespace registry {


enum class MessageAction {
    REGISTER,   // Register an agent with CXI address
    QUERY,      // Query CXI address for an agent
    UNREGISTER  // Unregister an agent (future use)
};

enum class ResponseStatus {
    OK,         // Operation successful
    ERROR,      // General error
    NOT_FOUND   // Agent not found
};

inline std::string to_string(MessageAction action) {
    switch (action) {
        case MessageAction::REGISTER:   return "REGISTER";
        case MessageAction::QUERY:      return "QUERY";
        case MessageAction::UNREGISTER: return "UNREGISTER";
        default: return "UNKNOWN";
    }
}

inline std::string to_string(ResponseStatus status) {
    switch (status) {
        case ResponseStatus::OK:        return "OK";
        case ResponseStatus::ERROR:     return "ERROR";
        case ResponseStatus::NOT_FOUND: return "NOT_FOUND";
        default: return "UNKNOWN";
    }
}

inline MessageAction string_to_action(const std::string& action_str) {
    if (action_str == "REGISTER")   return MessageAction::REGISTER;
    if (action_str == "QUERY")      return MessageAction::QUERY;
    if (action_str == "UNREGISTER") return MessageAction::UNREGISTER;
    throw std::invalid_argument("Unknown action: " + action_str);
}

inline ResponseStatus string_to_status(const std::string& status_str) {
    if (status_str == "OK")        return ResponseStatus::OK;
    if (status_str == "ERROR")     return ResponseStatus::ERROR;
    if (status_str == "NOT_FOUND") return ResponseStatus::NOT_FOUND;
    throw std::invalid_argument("Unknown status: " + status_str);
}

struct RegistryMessage {
    MessageAction action;
    std::string agent_id;
    std::optional<std::string> cxi_address;  // Optional for QUERY requests
    
    RegistryMessage(MessageAction act, const std::string& id, const std::optional<std::string>& addr = std::nullopt)
        : action(act), agent_id(id), cxi_address(addr) {}
 
    std::string to_json() const {
        nlohmann::json j;
        j["action"] = to_string(action);
        j["agent_id"] = agent_id;
        if (cxi_address.has_value()) {
            j["cxi_address"] = cxi_address.value();
        }
        return j.dump();
    }

    static RegistryMessage from_json(const std::string& json_str) {
        nlohmann::json j = nlohmann::json::parse(json_str);
        
        MessageAction action = string_to_action(j["action"]);
        std::string agent_id = j["agent_id"];
        std::optional<std::string> cxi_address = std::nullopt;
        
        if (j.contains("cxi_address")) {
            cxi_address = j["cxi_address"];
        }
        
        return RegistryMessage(action, agent_id, cxi_address);
    }
};

struct RegistryResponse {
    ResponseStatus status;
    std::optional<std::string> cxi_address;  // Present for successful QUERY responses
    std::optional<std::string> message;      // Error message or additional info
    
    RegistryResponse(ResponseStatus stat, const std::optional<std::string>& addr = std::nullopt, 
                    const std::optional<std::string>& msg = std::nullopt)
        : status(stat), cxi_address(addr), message(msg) {}
    
    std::string to_json() const {
        nlohmann::json j;
        j["status"] = to_string(status);
        if (cxi_address.has_value()) {
            j["cxi_address"] = cxi_address.value();
        }
        if (message.has_value()) {
            j["message"] = message.value();
        }
        return j.dump();
    }
    
    static RegistryResponse from_json(const std::string& json_str) {
        nlohmann::json j = nlohmann::json::parse(json_str);
        
        ResponseStatus status = string_to_status(j["status"]);
        std::optional<std::string> cxi_address = std::nullopt;
        std::optional<std::string> message = std::nullopt;
        
        if (j.contains("cxi_address") && !j["cxi_address"].is_null()) {
            cxi_address = j["cxi_address"];
        }
        if (j.contains("message") && !j["message"].is_null()) {
            message = j["message"];
        }
        
        return RegistryResponse(status, cxi_address, message);
    }
};

namespace factory {

inline RegistryMessage register_message(const std::string& agent_id, const std::string& cxi_address) {
    return RegistryMessage(MessageAction::REGISTER, agent_id, cxi_address);
}

inline RegistryMessage query_message(const std::string& agent_id) {
    return RegistryMessage(MessageAction::QUERY, agent_id);
}

inline RegistryMessage unregister_message(const std::string& agent_id) {
    return RegistryMessage(MessageAction::UNREGISTER, agent_id);
}

inline RegistryResponse ok_response(const std::optional<std::string>& cxi_address = std::nullopt) {
    return RegistryResponse(ResponseStatus::OK, cxi_address);
}

inline RegistryResponse error_response(const std::string& error_msg) {
    return RegistryResponse(ResponseStatus::ERROR, std::nullopt, error_msg);
}

inline RegistryResponse not_found_response() {
    return RegistryResponse(ResponseStatus::NOT_FOUND);
}

}

} 
} 
