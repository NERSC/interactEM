#ifndef QUEUE_CLIENT_HPP
#define QUEUE_CLIENT_HPP

#include <capnp/message.h>
#include <nanobind/ndarray.h>

#include <string>
#include <thallium.hpp>
#include <vector>

#include "ndarray_info.hpp"
#include "serialization/capnproto_serializer.hpp"

namespace tl = thallium;
namespace nb = nanobind;

class QueueClient {
  tl::engine &m_engine;
  tl::remote_procedure m_push_rdma;
  tl::endpoint m_server;
  tl::provider_handle m_ph;

public:
  QueueClient(tl::engine &engine, const std::string &server_addr,
              uint16_t provider_id = 1)
      : m_engine(engine), m_push_rdma(engine.define("push_rdma")) {
    try {
      m_server = m_engine.lookup(server_addr);
      m_ph = tl::provider_handle(m_server, provider_id);
    } catch (const tl::margo_exception &ex) {
      throw;
    }
  }

  void push_rdma(const std::string &header, nb::ndarray<nb::numpy> data) {
    try {
      print_ndarray_info(data);
      auto [serialized_bytes, ndarray_data] =
          serialization::CapnProtoSerializer::serialize(header, data);

      // Prepare segments to send
      std::vector<std::pair<void *, std::size_t>> rdma_segments;

      // Add the Cap'n Proto message segment
      try {
        rdma_segments.emplace_back(
            reinterpret_cast<void *>(serialized_bytes.data()),
            serialized_bytes.size());
        std::cout << "Debug: Added Cap'n Proto message segment of size = "
                  << serialized_bytes.size() << " bytes." << std::endl;
      } catch (const std::exception &e) {
        std::cout << "Error while adding Cap'n Proto message segment: "
                  << e.what() << std::endl;
      }

      // Add the ndarray data segment
      try {
        rdma_segments.emplace_back(data.data(), data.nbytes());
        std::cout << "Debug: Added ndarray segment of size = " << data.size()
                  << " bytes." << std::endl;
      } catch (const std::exception &e) {
        std::cout << "Error while adding ndarray segment: " << e.what()
                  << std::endl;
      }

      if (rdma_segments.size() > std::numeric_limits<std::size_t>::max()) {
        std::cout << "Debug: Segments size (after adding) = "
                  << rdma_segments.size()
                  << " exceeds maximum acceptable limit." << std::endl;
        throw std::length_error(
            "Segments size exceeds maximum acceptable limit.");
      }

      // Create a bulk object with read-only access to the data
      std::cout << "Debug: Creating a bulk object for data exposure."
                << std::endl;
      tl::bulk bulk = m_engine.expose(rdma_segments, tl::bulk_mode::read_only);

      std::cout << "Debug: Calling remote procedure." << std::endl;
      m_push_rdma.on(m_ph)(bulk, serialized_bytes.size());
      std::cout << "Debug: Remote procedure called successfully." << std::endl;
    } catch (const tl::margo_exception &ex) {
      std::cerr << "Thallium exception: " << ex.what() << std::endl;
    } catch (const std::length_error &ex) {
      std::cerr << "Length error: " << ex.what() << std::endl;
    } catch (const std::exception &ex) {
      std::cerr << "General exception: " << ex.what() << std::endl;
    }
  }
};

#endif // QUEUE_CLIENT_HPP