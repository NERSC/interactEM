
#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <optional>
#include <thallium.hpp>
#include <thallium/serialization/stl/string.hpp>
#include "proto_type.hpp"
#include "op_mode.hpp"
#include "abt_manager.hpp"

namespace interactEM {

class EngineConfig {

    private:
        ProtocolType proto_type_;
        OperationMode op_mode_; // Operation mode (e.g., server, client) 
        std::optional<AbtManager> abt_manager_; // Argobots manager for thread management
        int port_ = 8080; // Default port for the engine
        std::string server_ip_ = "localhost"; // Default server IP

    public:
        EngineConfig() 
            : proto_type_(ProtocolType::TCP), op_mode_(OperationMode::SERVER) {}

        EngineConfig(const ProtocolType& proto_type, const OperationMode& op_mode) 
            : proto_type_(proto_type), op_mode_(op_mode) {}

        EngineConfig(const ProtocolType& proto_type, const OperationMode& op_mode, AbtManager&& abt_manager) 
            : proto_type_(proto_type), op_mode_(op_mode), abt_manager_(std::move(abt_manager)) {}

        EngineConfig(const ProtocolType& proto_type, const OperationMode& op_mode, AbtManager&& abt_manager, int port) 
            : proto_type_(proto_type), op_mode_(op_mode), abt_manager_(std::move(abt_manager)), port_(port) {}

        EngineConfig(const ProtocolType& proto_type, const OperationMode& op_mode, AbtManager&& abt_manager, int port, std::string server_ip) 
            : proto_type_(proto_type), op_mode_(op_mode), abt_manager_(std::move(abt_manager)), port_(port), server_ip_(server_ip) {}

        // Delete copy operations since AbtManager is not copyable
        EngineConfig(const EngineConfig& other) = delete;
        EngineConfig& operator=(const EngineConfig& other) = delete;
        
        // Allow move operations
        EngineConfig(EngineConfig&& other) = default;
        EngineConfig& operator=(EngineConfig&& other) = default;

        const ProtocolType& getProtocolType() const {
            return proto_type_;
        }

        int getPort() const {
            return port_;
        }

        std::string getServerIp() const {
            return server_ip_;
        }

        const OperationMode& getOpMode() const {
            return op_mode_;
        }

        AbtManager& getAbtManager() {
            if(!abt_manager_.has_value()) {
                throw std::runtime_error("AbtManager not set.");
            }
            return abt_manager_.value();
        }

        bool hasAbtManager() const {
            return abt_manager_.has_value();
        }

};

}