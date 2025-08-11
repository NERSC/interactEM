# InteractEM-RDMA

A high-performance RDMA (Remote Direct Memory Access) proxy service built with Mochi libraries for efficient inter-node communication in HPC environments.

## Overview

InteractEM-RDMA is a modular RDMA proxy system designed to facilitate efficient data transfer and communication between nodes in high-performance computing environments. The project leverages the Thallium framework (built on top of Mercury) and integrates with Argobots for lightweight threading support.

## Project Structure

```
interactEM-rdma/
├── CMakeLists.txt         # Main build configuration
├── src/                   # Core implementation files
├── include/               # Public header files
├── common/                # Common utilities and definitions
└── libs/                  # External library integrations
```

### Core Components (`src/` and `include/`)

#### Main Service Classes

- **`RdmaProxyService`** (`RdmaProxyService.hpp/.cpp`)
  - Main service orchestrator that coordinates all RDMA operations
  - Manages sender, receiver, and transporter components
  - Serves as the primary interface for RDMA proxy functionality

- **`OperatorSender`** (`op_sender.hpp/.cpp`)
  - Handles message sending from operators on a node to the RDMA proxy
  - Manages local operator-to-proxy communication
  - Implements message queuing and forwarding to the proxy service

- **`OperatorReceiver`** (`op_receiver.hpp/.cpp`)
  - Handles incoming messages that reach the RDMA proxy
  - Manages message routing and delivery to destination operators
  - Processes received messages and ensures proper delivery to target operators

- **`PrxTransporter`** (`prx_transporter.hpp/.cpp`)
  - Core transport layer implementation
  - Integrates `EngProvider` (Thallium provider for RDMA operations)
  - Manages `EngDispatcher` for operation handling
  - Provides abstraction over different transport protocols

### Common Utilities (`common/`)

Contains shared definitions and utilities used across the entire project:

- **`op_mode.hpp`**: Defines operation modes (SERVER, CLIENT, UNKNOWN) using Thallium constants
- **`proto_type.hpp`**: Enumerates supported protocol types (TCP, UDP, CXI, etc.) with conversion utilities
- **`abt_type.hpp`**: Argobots-related type definitions including:
  - Schedule types (DEFAULT, FIFO, ROUND_ROBIN, PRIORITY)
  - Pool types (DEFAULT, FAST, SLOW, HIGH_PRIORITY)

### External Libraries (`libs/`)

Manages integration with external dependencies:

- **`thallium/`**: Thallium framework integration for RPC and RDMA operations
- **`argobots/`**: Argobots lightweight threading library integration
- **`rdma_external_libs`**: Meta-library that aggregates all external dependencies

## Build Instructions

### Prerequisites

Ensure you have the following installed:
- CMake 3.15+
- C++17 compatible compiler
- Thallium library and dependencies
- Argobots library

### Building the Project

```bash
# Create build directory
mkdir build && cd build

# Configure with CMake
cmake ..

# Build the project
make

# The executable will be created as 'rdma_proxy'
```
