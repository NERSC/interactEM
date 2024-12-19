#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>

#include <thallium.hpp>

#include "QueueClient.hpp"
#include "QueueProvider.hpp"

namespace nb = nanobind;
namespace tl = thallium;
using namespace nb::literals;

namespace interactEM {
class PyQueueClient {
public:
  PyQueueClient(const std::string &protocol, const std::string &server_addr,
                uint16_t provider_id = 1)
      : engine(protocol, THALLIUM_CLIENT_MODE),
        client(engine, server_addr, provider_id) {}

  void push_rdma(const std::string &header, nb::ndarray<nb::numpy> data) {
    client.push_rdma(header, data);
  }

private:
  tl::engine engine;
  QueueClient client;
};

class PyQueueProvider {
public:
  PyQueueProvider(const std::string &protocol, uint16_t provider_id = 1)
      : engine(protocol, THALLIUM_SERVER_MODE), provider(engine, provider_id) {}

  PyMessage pull() { return provider.pull(); }

  std::string get_address() const { return engine.self(); }

  void wait_for_finalize() { engine.wait_for_finalize(); }

private:
  tl::engine engine;
  QueueProvider provider;
};

NB_MODULE(_thallium, m) {
  nb::class_<PyMessage>(m, "Message")
      .def(nb::init<const std::string &, const nb::ndarray<nb::numpy> &>(),
           "header"_a, "data"_a)
      .def_rw("header", &PyMessage::header)
      .def_rw("data", &PyMessage::data);

  nb::class_<PyQueueClient>(m, "QueueClient")
      .def(nb::init<const std::string &, const std::string &, uint16_t>(),
           "protocol"_a, "server_addr"_a, "provider_id"_a = 1)
      .def("push_rdma", &PyQueueClient::push_rdma, "header"_a, "data"_a);

  nb::class_<PyQueueProvider>(m, "QueueProvider")
      .def(nb::init<const std::string &, uint16_t>(), "protocol"_a,
           "provider_id"_a = 1)
      .def("pull", &PyQueueProvider::pull)
      .def("get_address", &PyQueueProvider::get_address)
      .def("wait_for_finalize", &PyQueueProvider::wait_for_finalize);
}
} // namespace interactEM