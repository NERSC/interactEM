
#include <iostream>
#include <string>
#include <vector>
#include <thallium.hpp>
#include "abt_type.hpp"

namespace interactEM {

namespace tl = thallium;

class AbtConfig {

    private:
        int num_xstreams_; // Number of execution streams
        int num_pools_;    // Number of Argobots pools
        tl::pool::access pool_access_; // Access type for the Argobots pool
        tl::scheduler::predef scheduler_type_; // Predefined scheduler type

    public:
        AbtConfig() = default;
    
};

}