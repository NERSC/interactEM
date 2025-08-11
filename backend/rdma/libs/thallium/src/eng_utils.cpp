
#include "eng_utils.hpp"

namespace interactEM {

// Specialized version for std::vector<char>
std::vector<std::pair<void*, size_t>> EngUtils::create_segments(const std::vector<char>& data) {
    std::vector<std::pair<void*, size_t>> segments(1);
    segments[0].first = const_cast<void*>(static_cast<const void*>(data.data()));
    segments[0].second = data.size();
    return segments;
}

}