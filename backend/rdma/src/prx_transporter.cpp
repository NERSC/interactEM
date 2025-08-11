#include "prx_transporter.hpp"

namespace interactEM {

void ProxyTransporter::stop() {
    eng_registry_->stop();
    eng_provider_->stop();
    // eng_dispatcher_.stop();
}

ProxyTransporter::~ProxyTransporter() {
    this->stop();
}

}

