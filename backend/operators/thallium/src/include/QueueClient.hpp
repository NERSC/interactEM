#ifndef INCLUDE_QUEUE_CLIENT_H
#define INCLUDE_QUEUE_CLIENT_H

#include <capnp/message.h>
#include <nanobind/ndarray.h>

#include <string>
#include <thallium.hpp>
#include <vector>

#include "ndarray_info.hpp"
#include "serialization/capnproto_serializer.hpp"

namespace interactEM {

namespace tl = thallium;
namespace nb = nanobind;

class QueueClient {
  std::shared_ptr<tl::engine> m_engine;
  tl::remote_procedure m_push_rdma;
  tl::endpoint m_server;
  tl::provider_handle m_ph;

  QueueClient(std::shared_ptr<tl::engine> engine,
              const std::string &server_addr, uint16_t provider_id = 1)
      : m_engine(engine), m_push_rdma(engine->define("push_rdma")) {
    try {
      m_server = m_engine->lookup(server_addr);
      m_ph = tl::provider_handle(m_server, provider_id);
    } catch (const tl::margo_exception &ex) {
      throw;
    }
  }

public:
  // Use factory to allocate on the heap
  static std::unique_ptr<QueueClient> create(margo_instance_id mid,
                                             const std::string &server_addr,
                                             uint16_t provider_id = 1) {
    // We attach to existing engine with this call
    auto engine = std::make_shared<tl::engine>(mid, false);
    return std::unique_ptr<QueueClient>(
        new QueueClient(engine, server_addr, provider_id));
  }

  void push_rdma(const std::string &header, nb::ndarray<nb::numpy> data) {
    try {
      // print_ndarray_info(data);
      auto [serialized_bytes, ndarray_data] =
          serialization::Serializer::serialize(
              serialization::SerializationType::FlatBuffers, header, data);

      // Prepare segments to send
      std::vector<std::pair<void *, std::size_t>> rdma_segments;

      // Add the Cap'n Proto message segment
      rdma_segments.emplace_back(
          reinterpret_cast<void *>(serialized_bytes.data()),
          serialized_bytes.size());

      // Add the ndarray data segment
      rdma_segments.emplace_back(data.data(), data.nbytes());

      // Create a bulk object with read-only access to the data
      tl::bulk bulk = m_engine->expose(rdma_segments, tl::bulk_mode::read_only);
      m_push_rdma.on(m_ph)(bulk, serialized_bytes.size());
    } catch (const tl::margo_exception &ex) {
      std::cerr << "Thallium exception: " << ex.what() << std::endl;
    } catch (const std::exception &ex) {
      std::cerr << "Exception: " << ex.what() << std::endl;
    }
  }
};

} // namespace interactEM

#endif /* INCLUDE_QUEUE_CLIENT_H */
