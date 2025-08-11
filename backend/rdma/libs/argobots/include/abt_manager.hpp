
#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <thallium.hpp>
#include <thallium/serialization/stl/string.hpp>
#include "abt_config.hpp"

namespace interactEM {

namespace tl = thallium;

class AbtManager {

    private:
        // AbtPool pool_; // Custom Argobots pool
        // AbtScheduler scheduler_; // Custom Argobots scheduler
        std::vector<tl::managed<tl::xstream>> execution_streams_;
        tl::managed<tl::pool> thread_pool_;
        bool is_initialized_;
        
        static tl::abt* global_abt_scope_;
        static int instance_count_;

    public:
        AbtManager() : is_initialized_(false) {}
        AbtManager(const AbtConfig& config) {}
        ~AbtManager();
        
        AbtManager(const AbtManager& other) = delete;
        AbtManager& operator=(const AbtManager& other) = delete;
        
        AbtManager(AbtManager&& other) = default;
        AbtManager& operator=(AbtManager&& other) = default;
        
        void initialize();
        void finalize();
        tl::pool& getPool() {return *thread_pool_;}
};

}
