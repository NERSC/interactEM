

#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <optional>
#include <unordered_map>
#include <thread>
#include <functional>
#include <thallium.hpp>
#include <thallium/serialization/stl/string.hpp>
#include "socket_client.hpp"
#include "cxi_registry.hpp"

namespace interactEM {

namespace tl = thallium;

class EngRegistry {

private:
    SocketClient socket_client_; // Client for pushing/pull agent specific CXI address for provider
    static std::unordered_map<std::string, std::string> cxi_addresses_; // Maps agent IDs to CXI addresses

    EngRegistry(int port, const std::string& server_ip) 
        : socket_client_(port, server_ip) {
    }

public:

    static std::unique_ptr<EngRegistry> create(int port, const std::string& server_ip = "localhost") {
        return std::unique_ptr<EngRegistry>(new EngRegistry(port, server_ip));
    }

    ~EngRegistry() {
        this->stop();
    }

    void stop(){
        socket_client_.~SocketClient();
    }

    // Push CXI address to the server
    void pushCxiAddress(const std::string& agent_id, const std::string& cxi_address) {
        if (!socket_client_.connectToServer()) {
            std::cerr << "Failed to connect to server" << std::endl;
            return;
        }

        auto message = registry::factory::register_message(agent_id, cxi_address);
        std::string json_message = message.to_json() + "\n";
        
        if (!socket_client_.sendMessage(json_message)) {
            std::cerr << "Failed to send message" << std::endl;
        }
    }

    // Pull CXI address from the server
    void pullCxiAddress(const std::string& agent_id) {
        
        if (!socket_client_.connectToServer()) {
            std::cerr << "Failed to connect to server" << std::endl;
            return;
        }

        auto message = registry::factory::query_message(agent_id);
        std::string json_message = message.to_json() + "\n";
        
        if (!socket_client_.sendMessage(json_message)) {
            std::cerr << "Failed to send message" << std::endl;
            return;
        }
        
        std::string response_str = socket_client_.receiveMessage();
        if (response_str.empty()) {
            std::cerr << "No response received" << std::endl;
            return;
        }
        
        try {
            auto response = registry::RegistryResponse::from_json(response_str);
            
            switch (response.status) {
                case registry::ResponseStatus::OK:
                    if (response.cxi_address.has_value()) {
                        cxi_addresses_[agent_id] = response.cxi_address.value();
                        std::cout << "CXI address for agent: " << agent_id 
                                  << " is " << cxi_addresses_[agent_id] << std::endl;
                    }
                    break;
                    
                case registry::ResponseStatus::NOT_FOUND:
                    std::cout << "No CXI address found for agent: " << agent_id << std::endl;
                    break;
                    
                case registry::ResponseStatus::ERROR:
                    std::cerr << "Server error";
                    if (response.message.has_value()) {
                        std::cerr << ": " << response.message.value();
                    }
                    std::cerr << std::endl;
                    break;
            }
        } catch (const std::exception& e) {
            std::cerr << "Failed to parse response: " << e.what() << std::endl;
        }
    }

    // Get the CXI address for an agent
    std::optional<std::string> getCxiAddress(const std::string& agent_id) const {
        auto it = cxi_addresses_.find(agent_id);
        if (it != cxi_addresses_.end()) {
            return it->second;
        }
        return std::nullopt;
    }

    SocketClient& getSocketClient() {
        return socket_client_;
    }

};

}