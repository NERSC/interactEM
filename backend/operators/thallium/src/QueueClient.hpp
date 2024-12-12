#ifndef QUEUE_CLIENT_HPP
#define QUEUE_CLIENT_HPP

#include <thallium.hpp>
#include <string>
#include <vector>

namespace tl = thallium;

class QueueClient
{
    tl::engine &m_engine;
    tl::remote_procedure m_push;
    tl::remote_procedure m_push_rdma;
    tl::endpoint m_server;
    tl::provider_handle m_ph;

public:
    QueueClient(tl::engine &engine, const std::string &server_addr, uint16_t provider_id = 1)
        : m_engine(engine),
          m_push(engine.define("push")),
          m_push_rdma(engine.define("push_rdma"))
    {
        try
        {
            m_server = m_engine.lookup(server_addr);
            std::cout << "Server address looked up: " << server_addr << std::endl;
            std::cout << "Endpoint: " << m_server.get_addr() << std::endl;
            m_ph = tl::provider_handle(m_server, provider_id);
        }
        catch (const tl::margo_exception &ex)
        {
            std::cerr << "Error during address lookup: " << ex.what() << std::endl;
            throw;
        }
    }

    void push(const std::string &header, const std::vector<uint8_t> &data)
    {
        try
        {
            int rc = m_push.on(m_ph)(header, data);
            std::cout << "Message pushed: " << header << ". RC: " << rc << std::endl;
        }
        catch (const tl::margo_exception &ex)
        {
            std::cerr << "Error during RPC call: " << ex.what() << std::endl;
            throw;
        }
        catch (const std::exception &ex)
        {
            std::cerr << "Error during RPC call: " << ex.what() << std::endl;
            throw;
        }
    }

    void push_rdma(const std::string &header, const std::vector<uint8_t> &data)
    {
        try
        {
            std::vector<std::pair<void *, std::size_t>> segments(2);
            segments[0].first = (void *)header.data();
            segments[0].second = header.size();
            segments[1].first = (void *)data.data();
            segments[1].second = data.size();
            tl::bulk bulk = m_engine.expose(segments, tl::bulk_mode::read_only);

            m_push_rdma.on(m_ph)(bulk, header.size());
            std::cout << "Message pushed via RDMA: " << header << std::endl;
        }
        catch (const tl::margo_exception &ex)
        {
            std::cerr << "Error during RDMA call: " << ex.what() << std::endl;
            throw;
        }
        catch (const std::exception &ex)
        {
            std::cerr << "Error during RDMA call: " << ex.what() << std::endl;
            throw;
        }
    }
};

#endif // QUEUE_CLIENT_HPP