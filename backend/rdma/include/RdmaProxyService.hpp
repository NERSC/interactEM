
/**
 * @file RdmaProxyService.hpp
 * @brief Main service orchestrator that coordinates all RDMA operations
 * 
 * RdmaProxyService serves as the primary interface for RDMA proxy functionality,
 * managing sender, receiver, and transporter components to facilitate efficient
 * inter-node communication in HPC environments.
 */

#include <iostream>
#include <string>
#include <thallium.hpp>
#include "op_receiver.hpp"
#include "op_sender.hpp"
#include "prx_transporter.hpp"

namespace interactEM {

class RdmaProxyService {

    private:
        OpSender sender_;
        PrxTransporter transporter_;
        OpReceiver receiver_;

    public:
        RdmaProxyService() = default;
        ~RdmaProxyService() = default;

        // void initialize();
        void stop();
        
};

}