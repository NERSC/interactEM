#ifndef QUEUE_PROVIDER_HPP
#define QUEUE_PROVIDER_HPP

#include <capnp/serialize.h>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include <deque>
#include <thallium.hpp>
#include <thallium/serialization/stl/string.hpp>
#include <thallium/serialization/stl/vector.hpp>

#include "ndarray_info.hpp"
#include "serialization/capnproto_serializer.hpp"

namespace tl = thallium;
namespace nb = nanobind;

struct PyMessage {
  std::string header;
  nb::ndarray<nb::numpy> data;
};

class QueueProvider : public tl::provider<QueueProvider> {
private:
  std::deque<PyMessage> queue;
  tl::mutex mtx;
  tl::condition_variable cv;

public:
  QueueProvider(tl::engine &engine, uint16_t provider_id = 1)
      : tl::provider<QueueProvider>(engine, provider_id) {
    define("push_rdma", &QueueProvider::push_rdma);
  }

  ~QueueProvider() {
    std::cout << "Debug: QueueProvider destructor called." << std::endl;
  }

  void push_rdma(const tl::request &req, tl::bulk &remote_bulk,
                 std::size_t header_size) {
    tl::endpoint ep = req.get_endpoint();
    std::cout << "Debug: Received request from endpoint: " << ep.get_addr()
              << std::endl;

    // Get the size of the bulk data
    std::size_t bulk_size = remote_bulk.size();
    size_t data_size = bulk_size - header_size;
    size_t data_offset = header_size;

    // Allocate buffers for header/data and expose them for RDMA
    std::vector<char> header_buffer(header_size);
    std::vector<char> data_buffer(data_size);
    std::vector<std::pair<void *, std::size_t>> local_segments(2);
    local_segments[0].first = header_buffer.data();
    local_segments[0].second = header_buffer.size();
    local_segments[1].first = data_buffer.data();
    local_segments[1].second = data_buffer.size();
    tl::bulk local_bulk =
        get_engine().expose(local_segments, tl::bulk_mode::write_only);

    // RDMA transfer
    remote_bulk(0, header_size).on(ep) >> local_bulk(0, header_size);
    remote_bulk(data_offset, data_size).on(ep) >>
        local_bulk(data_offset, data_size);

    try {
      auto [message_header, ndarray_data] =
          serialization::Serializer::deserialize(
              serialization::SerializationType::FlatBuffers, header_buffer,
              data_buffer);
      print_ndarray_info(ndarray_data);

      // Push the message into the queue
      {
        std::lock_guard<tl::mutex> lock(mtx);
        PyMessage msg;
        msg.header = message_header;
        msg.data = ndarray_data;
        queue.push_back(msg);
        std::cout << "Debug: Pushed message to queue." << std::endl;
      }

      cv.notify_one();
      req.respond();
    } catch (const kj::Exception &e) {
      std::cerr << "Error during message deserialization: "
                << e.getDescription().cStr() << std::endl;
      req.respond(); // Respond to the request even on error
      return;
    }

    std::cout << "Debug: Successfully processed the push_rdma request."
              << std::endl;
  }
  PyMessage pull() {
    std::unique_lock<tl::mutex> lock(mtx);
    cv.wait(lock, [this] { return !queue.empty(); });
    PyMessage msg = queue.front();
    queue.pop_front();
    return msg;
  }
};

#endif // QUEUE_PROVIDER_HPP