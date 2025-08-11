
#include "abt_manager.hpp"

namespace interactEM {

namespace tl = thallium;

tl::abt* AbtManager::global_abt_scope_ = nullptr;
int AbtManager::instance_count_ = 0;

void AbtManager::initialize() {
    if (is_initialized_) {
        return; 
    }
    
    // Initialize Argobots globally only once
    if (global_abt_scope_ == nullptr) {
        global_abt_scope_ = new tl::abt();
    }
    instance_count_++;

    thread_pool_ = tl::pool::create(tl::pool::access::spmc);
    for(int i=0; i<10; i++){
        tl::managed<tl::xstream> es 
            = tl::xstream::create(tl::scheduler::predef::deflt, *thread_pool_);
        execution_streams_.push_back(std::move(es));
    }
    
    is_initialized_ = true;
}

void AbtManager::finalize() {
    if (!is_initialized_) {
        return;
    }
    
    // Clean up execution streams first
    for(auto& es : execution_streams_) {
        es->join();
    }
    execution_streams_.clear();
    
    // Then release the thread pool
    thread_pool_.release();
    
    // Only finalize Argobots when last instance is destroyed
    instance_count_--;
    if (instance_count_ == 0 && global_abt_scope_ != nullptr) {
        delete global_abt_scope_;
        global_abt_scope_ = nullptr;
    }
    
    is_initialized_ = false;
}

AbtManager::~AbtManager() {
    if (is_initialized_) {
        this->finalize();
    }
}

}