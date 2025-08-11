
#pragma once

#include <vector>
#include <array>
#include <type_traits>
#include <cstring>
#include <thallium.hpp>
#include "eng_config.hpp"

namespace interactEM {

namespace tl = thallium;

class EngManager {
    
    private:
        EngineConfig config_;
        tl::engine engine_;
        
        static tl::engine createEngine(const EngineConfig& config) {
            std::string protocol = to_string(config.getProtocolType());
            OperationMode op_mode = config.getOpMode();
            std::cout << "Creating Thallium engine with protocol: " 
                    << protocol << " and operation mode: " 
                    << (op_mode == OperationMode::SERVER ? "Server" : "Client") << std::endl;
            return tl::engine(protocol, static_cast<int>(op_mode));
        }
        
    public:
        EngManager(EngineConfig&& config)
            : config_(std::move(config))
            , engine_(createEngine(config_))
        {
            // initialize the Argobots manager if it exists
            if (hasAbtManager()) {
                getAbtManager().initialize();
            }
        }
        
        tl::engine& getEngine() { return engine_; }
        
        const tl::engine& getEngine() const { return engine_; }
        
        const EngineConfig& getConfig() const { return config_; }
        
        bool hasAbtManager() const { return this->config_.hasAbtManager();}
        
        AbtManager& getAbtManager() { return this->config_.getAbtManager();}

};

}