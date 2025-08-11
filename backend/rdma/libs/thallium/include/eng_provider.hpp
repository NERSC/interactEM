
#pragma once

#include <vector>
#include <array>
#include <type_traits>
#include <cstring>
#include <thallium.hpp>
#include "eng_config.hpp"
#include "eng_manager.hpp"
#include "eng_utils.hpp"
#include "eng_registry.hpp"

namespace interactEM {

namespace tl = thallium;

class EngProvider : public EngManager, public tl::provider<EngProvider> {

    private:

        // EngRegistry m_registry_; // Registry for managing CXI addresses
        // static std::deque<std::unique_ptr<PyMessage>> queue; // Queue for temp storage, later route to OperatorReceiver

        tl::remote_procedure m_rdma_pull; // RDMA pull operation

        EngProvider(EngineConfig&& config, uint16_t provider_id=-1)
            : EngManager(std::move(config)),
              tl::provider<EngProvider>(this->getEngine(), provider_id) {
            if (this->hasAbtManager()) {
                m_rdma_pull = define("rdma_pull", &EngProvider::rdma_pull,
                    this->getAbtManager().getPool());
            } else {
                m_rdma_pull = define("rdma_pull", &EngProvider::rdma_pull);
            }
            getEngine().push_finalize_callback(this, [p=this]() {delete p;});
            // this->initialize();
        }

    public:
        
        static std::unique_ptr<EngProvider> create(EngineConfig&& config, uint16_t provider_id=-1) {
            return std::unique_ptr<EngProvider>(new EngProvider(std::move(config), provider_id));
        }

        ~EngProvider();

        // void initialize();
        void stop();

        // Provide access to the engine
        tl::engine& getEngine() { return EngManager::getEngine(); }
        const tl::engine& getEngine() const { return EngManager::getEngine(); }

        void rdma_pull(const tl::request& req, tl::bulk& b);

};

}