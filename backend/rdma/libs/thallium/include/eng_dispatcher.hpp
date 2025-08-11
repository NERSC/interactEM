
#pragma once

#include <vector>
#include <array>
#include <type_traits>
#include <cstring>
#include <thallium.hpp>
#include "eng_config.hpp"
#include "eng_manager.hpp"
#include "eng_utils.hpp"

namespace interactEM {

namespace tl = thallium;

class EngDispatcher : public EngManager {
    
    private:

        tl::remote_procedure m_rdma_push; // RDMA push operation
        tl::endpoint m_endpoint; // Endpoint for the provider
        tl::provider_handle m_provider_handle; // Provider handle for the dispatcher

        EngDispatcher(EngineConfig&& config, uint16_t provider_id=-1)
            : EngManager(std::move(config)), 
              m_rdma_push(getEngine().define("rdma_pull")),
              m_endpoint(getEngine().lookup(config.getServerIp())),
              m_provider_handle(tl::provider_handle(m_endpoint, provider_id))
        {
            getEngine().push_finalize_callback(this, [p=this]() {delete p;});    
            // this->initialize();
        }

    public:
        
        static std::unique_ptr<EngDispatcher> create(EngineConfig&& config) {
            return std::unique_ptr<EngDispatcher>(new EngDispatcher(std::move(config)));
        }

        void stop();

        // Provide access to the engine
        tl::engine& getEngine() { return EngManager::getEngine(); }
        const tl::engine& getEngine() const { return EngManager::getEngine(); }

    
};

}