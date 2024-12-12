#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <thallium.hpp>
#include "QueueProvider.hpp"
#include "QueueClient.hpp"

namespace nb = nanobind;
namespace tl = thallium;
using namespace nb::literals;

class PyQueueClient
{
public:
    PyQueueClient(const std::string &protocol, const std::string &server_addr, uint16_t provider_id = 1)
        : engine(protocol, THALLIUM_CLIENT_MODE), client(engine, server_addr, provider_id) {}

    void push(const std::string &header, const std::vector<uint8_t> &data)
    {
        client.push(header, data);
    }

    void push_rdma(const std::string &header, const std::vector<uint8_t> &data)
    {
        client.push_rdma(header, data);
    }

private:
    tl::engine engine;
    QueueClient client;
};

class PyQueueProvider
{
public:
    PyQueueProvider(const std::string &protocol, uint16_t provider_id = 1)
        : engine(protocol, THALLIUM_SERVER_MODE), provider(engine, provider_id) {}

    Message pull()
    {
        return provider.pull();
    }

    std::string get_address() const
    {
        return engine.self();
    }

    void wait_for_finalize()
    {
        engine.wait_for_finalize();
    }

private:
    tl::engine engine;
    QueueProvider provider;
};

NB_MODULE(_thallium, m)
{
    nb::class_<Message>(m, "Message")
        .def(nb::init<const std::string &, const std::vector<uint8_t> &>(),
             "header"_a, "data"_a)
        .def_rw("header", &Message::header)
        .def_rw("data", &Message::data);

    nb::class_<PyQueueClient>(m, "QueueClient")
        .def(nb::init<const std::string &, const std::string &, uint16_t>(),
             "protocol"_a, "server_addr"_a, "provider_id"_a = 1)
        .def("push", &PyQueueClient::push, "header"_a, "data"_a)
        .def("push_rdma", &PyQueueClient::push_rdma, "header"_a, "data"_a);

    nb::class_<PyQueueProvider>(m, "QueueProvider")
        .def(nb::init<const std::string &, uint16_t>(),
             "protocol"_a, "provider_id"_a = 1)
        .def("pull", &PyQueueProvider::pull)
        .def("get_address", &PyQueueProvider::get_address)
        .def("wait_for_finalize", &PyQueueProvider::wait_for_finalize);
}