
/**
 * @file op_receiver.hpp
 * @brief Handles incoming messages that reach the RDMA proxy and manages routing to destination operators
 * 
 * OpReceiver is responsible for processing messages received by the RDMA proxy from remote sources
 * and ensuring proper delivery to the appropriate destination operators on the local node.
 */

#include <iostream>
#include <string>
#include <thallium.hpp>

namespace interactEM {

class OperatorReceiver {

    private:

    public:
        OperatorReceiver() = default;  

        // void initialize();
        // void stop();
};

}