
/**
 * @file prx_transporter.hpp
 * @brief Core transport layer implementation for RDMA operations
 * 
 * ProxyTransporter provides abstraction over different transport protocols,
 * integrating EngProvider (Thallium provider for RDMA operations) and
 * EngDispatcher for operation handling across various network protocols.
 */

#include <iostream>
#include <string>
#include <thallium.hpp>
// #include "eng_dispatcher.hpp"
#include "eng_provider.hpp"
#include "eng_registry.hpp"

namespace interactEM {

class ProxyTransporter{

    private:
        // std::unique_ptr<EngDispatcher> eng_dispatcher_; // Dispatcher for handling operations (sender / client)
        std::unique_ptr<EngProvider> eng_provider_; // Thallium provider for RDMA operations (receiver / server)
        std::unique_ptr<EngRegistry> eng_registry_; // Registry for managing CXI addresses
        
        ProxyTransporter(EngineConfig&& config, uint16_t provider_id=-1)
        : eng_registry_(EngRegistry::create(config.getPort(), config.getServerIp())),
            eng_provider_(EngProvider::create(std::move(config), provider_id))
        {
            // this->initialize();
        }
        
    public:
        ProxyTransporter() = default;
        ~ProxyTransporter();

        static std::unique_ptr<ProxyTransporter> create(EngineConfig&& config, uint16_t provider_id=-1) {
            return std::unique_ptr<ProxyTransporter>(new ProxyTransporter(std::move(config), provider_id));
        }

        // void initialize();
        void stop();

        void pushCxiAddress(const std::string& agent_id, const std::string& cxi_address) {
            eng_registry_->pushCxiAddress(agent_id, cxi_address);
        }

        void pullCxiAddress(const std::string& agent_id) {
            eng_registry_->pullCxiAddress(agent_id);
        }

        std::optional<std::string> getCxiAddress(const std::string& agent_id) const {
            return eng_registry_->getCxiAddress(agent_id);
        }

};

}