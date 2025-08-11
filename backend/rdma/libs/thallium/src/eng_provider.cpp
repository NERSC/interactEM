#include "eng_provider.hpp"

namespace interactEM {

EngProvider::~EngProvider(){
    this->stop();
}

// void EngProvider::initialize(){
//     m_registry_.pushCxiAddress("default_agent", "default_operator", "default_cxi_address");
// }

// Stop the RDMA engine
void EngProvider::stop() {
    m_rdma_pull.deregister();
    getEngine().pop_finalize_callback(this);
}

// RDMA push operation
void EngProvider::rdma_pull(const tl::request& req, tl::bulk& b) {
    // std::cout << "Executing RDMA push operation..." << std::endl;
    tl::endpoint ep = req.get_endpoint();
    std::vector<char> v(b.size());
    std::vector<std::pair<void*, size_t>> segments = EngUtils::create_segments(v);
    tl::bulk local = getEngine().expose(segments, tl::bulk_mode::write_only);
    // std::cout << "Exposing bulk with size: " << b.size() << std::endl;
    b.on(ep) >> local;
    // std::cout << "Server received bulk: ";
    // for(auto c : v) std::cout << c;
    // std::cout << std::endl;
    // std::cout << "RDMA push operation completed successfully." << std::endl;
    req.respond();
}

}