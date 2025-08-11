
#pragma once

#include <vector>
#include <array>
#include <type_traits>
#include <cstring>
#include <thallium.hpp>

namespace interactEM {

namespace tl = thallium;

class EngUtils {
    
    public:
        // Specialized version for std::vector<char>
        static std::vector<std::pair<void*, size_t>> create_segments(const std::vector<char>& data);

        // Template for std::vector and std::array (containers with .data() and .size())
        template<typename T>
        static std::vector<std::pair<void*, size_t>> create_segments(const std::vector<T>& data);
        
        template<typename T, size_t N>  
        static std::vector<std::pair<void*, size_t>> create_segments(const std::array<T, N>& data);

        // Template for C-style arrays
        template<typename T, size_t N>
        static std::vector<std::pair<void*, size_t>> create_segments(const T (&data)[N]);

        // Template for single objects 
        template<typename T>
        static std::vector<std::pair<void*, size_t>> create_segments_single(const T& data);


};

template<typename T>
std::vector<std::pair<void*, size_t>> EngUtils::create_segments(const std::vector<T>& data) {
    static_assert(std::is_same_v<T, char> ||
                 std::is_trivially_copyable_v<T>,
                 "Vector elements must be char or trivially copyable");
    
    std::vector<std::pair<void*, size_t>> segments(1);
    segments[0].first = const_cast<void*>(static_cast<const void*>(data.data()));
    segments[0].second = data.size() * sizeof(T);
    return segments;
}

template<typename T, size_t N>  
std::vector<std::pair<void*, size_t>> EngUtils::create_segments(const std::array<T, N>& data) {
    static_assert(std::is_trivially_copyable_v<T>,
                 "Array elements must be trivially copyable");
    
    std::vector<std::pair<void*, size_t>> segments(1);
    segments[0].first = const_cast<void*>(static_cast<const void*>(data.data()));
    segments[0].second = N * sizeof(T);
    return segments;
}

template<typename T, size_t N>
std::vector<std::pair<void*, size_t>> EngUtils::create_segments(const T (&data)[N]) {
    static_assert(std::is_trivially_copyable_v<T>, 
                 "Array elements must be trivially copyable");
    
    std::vector<std::pair<void*, size_t>> segments(1);
    segments[0].first = const_cast<void*>(static_cast<const void*>(data));
    segments[0].second = N * sizeof(T);
    return segments;
}

template<typename T>
std::vector<std::pair<void*, size_t>> EngUtils::create_segments_single(const T& data) {
    static_assert(std::is_trivially_copyable_v<T>, 
                 "Type must be trivially copyable for RDMA");
    
    std::vector<std::pair<void*, size_t>> segments(1);
    segments[0].first = const_cast<void*>(static_cast<const void*>(&data));
    segments[0].second = sizeof(T);
    return segments;
}

}