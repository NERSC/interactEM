#include <memory>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unique_ptr.h>

#include <thallium.hpp>

#include "QueueClient.hpp"
#include "QueueProvider.hpp"

namespace nb = nanobind;
namespace tl = thallium;
using namespace nb::literals;

namespace interactEM {

enum class EngineMode {
  SERVER = THALLIUM_SERVER_MODE,
  CLIENT = THALLIUM_CLIENT_MODE
};

class PyEngine {
public:
  PyEngine(const std::string &protocol, const EngineMode mode)
      : m_engine(protocol, static_cast<int>(mode)) {}

  std::string get_address() const { return m_engine.self(); }

  void wait_for_finalize() { m_engine.wait_for_finalize(); }

  margo_instance_id get_id() const { return m_engine.get_margo_instance(); }

private:
  tl::engine m_engine;
};

typedef std::unique_ptr<PyMessage, nb::deleter<PyMessage>>
    PyMessagePtrWithDeleter;

class PyQueueClient {
public:
  PyQueueClient(const PyEngine &engine, const std::string &server_addr,
                const uint16_t provider_id = 1) {
    m_client = QueueClient::create(engine.get_id(), server_addr, provider_id);
  }

  void push_rdma(PyMessagePtrWithDeleter msg) {
    m_client->push_rdma(msg->header, msg->data);
  }

private:
  std::unique_ptr<QueueClient> m_client;
};

class PyQueueProvider {
public:
  PyQueueProvider(const PyEngine &engine, const uint16_t provider_id) {
    provider = QueueProvider::create(engine.get_id(), provider_id);
  }

  PyMessagePtrWithDeleter pull() {
    auto msg = provider->pull();
    return PyMessagePtrWithDeleter(new PyMessage(std::move(*msg)));
  }

private:
  std::unique_ptr<QueueProvider> provider;
};

NB_MODULE(_thallium, m) {
  nb::enum_<interactEM::EngineMode>(m, "EngineMode")
      .value("SERVER", interactEM::EngineMode::SERVER)
      .value("CLIENT", interactEM::EngineMode::CLIENT);

  nb::class_<interactEM::PyEngine>(m, "Engine")
      .def(nb::init<const std::string &, const interactEM::EngineMode>(),
           "protocol"_a, "mode"_a)
      .def_prop_ro("address", &interactEM::PyEngine::get_address)
      .def("wait_for_finalize", &interactEM::PyEngine::wait_for_finalize);

  nb::class_<PyMessage>(m, "Message")
      .def(nb::init<const std::string, nb::ndarray<nb::numpy>>(), "header"_a,
           "data"_a)
      .def_rw("header", &PyMessage::header)
      // TODO: fix so we see that it is ndarray in python stubs
      // TODO: understand the rv policy better. This works (no leak warnings
      // emitted), but unsure if it is the correct thing to do...
      .def_rw("data", &PyMessage::data, nb::rv_policy::take_ownership);

  nb::class_<interactEM::PyQueueClient>(m, "QueueClient")
      .def(nb::init<const interactEM::PyEngine &, const std::string &,
                    const uint16_t>(),
           "engine"_a, "server_addr"_a, "provider_id"_a)
      .def("push_rdma", &interactEM::PyQueueClient::push_rdma, "msg"_a);

  nb::class_<interactEM::PyQueueProvider>(m, "QueueProvider")
      .def(nb::init<const interactEM::PyEngine &, const uint16_t>(), "engine"_a,
           "provider_id"_a)
      .def("pull", &interactEM::PyQueueProvider::pull);
}
} // namespace interactEM