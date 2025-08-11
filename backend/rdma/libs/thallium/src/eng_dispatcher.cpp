
#include "eng_dispatcher.hpp"

namespace interactEM {

EngDispatcher::~EngDispatcher() {
    this->stop();
}

void EngDispatcher::stop() {
    getEngine().pop_finalize_callback(this);
}

}