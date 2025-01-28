#ifndef INCLUDE_QUEUE_PROVIDER_H
#define INCLUDE_QUEUE_PROVIDER_H

#include <capnp/serialize.h>
#include <memory>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <vector>

#include <deque>
#include <thallium.hpp>
#include <thallium/serialization/stl/string.hpp>
#include <thallium/serialization/stl/vector.hpp>

#include "ndarray_info.hpp"
#include "serialization/serializer.hpp"

namespace interactEM {
namespace tl = thallium;
namespace nb = nanobind;

typedef std::vector<char> buffer_t;
typedef std::unique_ptr<buffer_t> buffer_ptr_t;

struct PyMessage {
  std::string header;
  nb::ndarray<nb::numpy> data;

  // Constructor for creating message without buffer
  PyMessage(std::string h, nb::ndarray<nb::numpy> d)
      : header(std::move(h)), data(std::move(d)) {}

  // Constructor for creating message with buffer
  PyMessage(std::string h, nb::ndarray<nb::numpy> d, buffer_ptr_t &&db)
      : header(std::move(h)), data(std::move(d)), buffer(std::move(db)) {}

  PyMessage(PyMessage &&other) noexcept
      : header(std::move(other.header)), data(std::move(other.data)),
        buffer(std::move(other.buffer)) {}

  PyMessage(const PyMessage &) = delete;
  PyMessage &operator=(const PyMessage &) = delete;

private:
  buffer_ptr_t buffer;
};

class QueueProvider : public tl::provider<QueueProvider> {
private:
  std::deque<std::unique_ptr<PyMessage>> queue;
  tl::mutex mtx;
  tl::condition_variable cv;
  tl::remote_procedure m_pull_rdma;
  std::unique_ptr<tl::engine> m_engine;

  QueueProvider(std::unique_ptr<tl::engine> engine, uint16_t provider_id = 1)
      : tl::provider<QueueProvider>(*engine, provider_id),
        m_pull_rdma(define("push_rdma", &QueueProvider::pull_rdma)) {
    get_engine().push_finalize_callback(this, [p = this]() { delete p; });
  }

public:
  ~QueueProvider() {
    m_pull_rdma.deregister();
    get_engine().pop_finalize_callback(this);
  }

  static std::unique_ptr<QueueProvider>
  create(std::unique_ptr<tl::engine> engine, uint16_t provider_id = 1) {
    return std::unique_ptr<QueueProvider>(
        new QueueProvider(std::move(engine), provider_id));
  }

  static std::unique_ptr<QueueProvider> create(margo_instance_id mid,
                                               uint16_t provider_id = 1) {
    return create(std::make_unique<tl::engine>(mid, false), provider_id);
  }

  void pull_rdma(const tl::request &req, tl::bulk &remote_bulk,
                 std::size_t header_size) {
    tl::endpoint ep = req.get_endpoint();

    // Get the size of the bulk data
    std::size_t bulk_size = remote_bulk.size();
    size_t data_size = bulk_size - header_size;
    size_t data_offset = header_size;

    // Allocate buffers for header/data and expose them for RDMA
    auto header_buffer = std::make_unique<std::vector<char>>(header_size);
    auto data_buffer = std::make_unique<std::vector<char>>(data_size);

    std::vector<std::pair<void *, std::size_t>> local_segments(2);
    local_segments[0].first = header_buffer->data();
    local_segments[0].second = header_buffer->size();
    local_segments[1].first = data_buffer->data();
    local_segments[1].second = data_buffer->size();

    tl::bulk local_bulk =
        get_engine().expose(local_segments, tl::bulk_mode::write_only);

    // RDMA transfer
    remote_bulk(0, header_size).on(ep) >> local_bulk(0, header_size);
    remote_bulk(data_offset, data_size).on(ep) >>
        local_bulk(data_offset, data_size);

    try {
      auto [message_header, ndarray_data] =
          serialization::Serializer::deserialize(*header_buffer, *data_buffer);

      // Push the message into the queue
      {
        std::lock_guard<tl::mutex> lock(mtx);
        queue.emplace_back(new PyMessage(std::move(message_header),
                                         std::move(ndarray_data),
                                         std::move(data_buffer)));
      }

      cv.notify_one();
      req.respond();

      // TODO: handle other exceptions
    } catch (const kj::Exception &e) {
      std::cerr << "Error during message deserialization: "
                << e.getDescription().cStr() << std::endl;
      req.respond();
      return;
    }
  }

  std::unique_ptr<PyMessage> pull() {
    std::unique_lock<tl::mutex> lock(mtx);
    // TODO: add timeout to this
    cv.wait(lock, [this] { return !queue.empty(); });
    auto msg = std::move(queue.front());
    queue.pop_front();
    return msg;
  }
};

} // namespace interactEM
#endif /* INCLUDE_QUEUE_PROVIDER_H */
