/**
 * @file abt_type.hpp
 * @brief Argobots-related type definitions for threading and scheduling
 * 
 * Contains type definitions for Argobots lightweight threading support,
 * including schedule types (FIFO, ROUND_ROBIN, PRIORITY) and pool types
 * (FAST, SLOW, HIGH_PRIORITY) for concurrent operation management.
 */

#pragma once

#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>

namespace interactEM {

enum class ScheduleType {
    SCHEDULE_TYPE_DEFAULT,
    SCHEDULE_TYPE_FIFO,
    SCHEDULE_TYPE_ROUND_ROBIN,
    SCHEDULE_TYPE_PRIORITY
};

enum class PoolType {
    POOL_TYPE_DEFAULT,
    POOL_TYPE_FAST,
    POOL_TYPE_SLOW,
    POOL_TYPE_HIGH_PRIORITY
};

};