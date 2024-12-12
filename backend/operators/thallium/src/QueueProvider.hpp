#ifndef QUEUE_PROVIDER_HPP
#define QUEUE_PROVIDER_HPP

#include <thallium.hpp>
#include <thallium/serialization/stl/string.hpp>
#include <thallium/serialization/stl/vector.hpp>
#include <deque>
#include <string>
#include <vector>

namespace tl = thallium;

struct Message
{
    std::string header;
    std::vector<uint8_t> data;
};

class QueueProvider : public tl::provider<QueueProvider>
{
private:
    std::deque<Message> queue;
    tl::mutex mtx;
    tl::condition_variable cv;

    int push(const std::string &header, const std::vector<uint8_t> &data)
    {
        {
            std::lock_guard<tl::mutex> lock(mtx);
            Message msg;
            msg.header = header;
            msg.data = data;
            queue.push_back(msg);
        }
        cv.notify_one();
        return 42;
    }

    void push_rdma(const tl::request &req, tl::bulk &bulk, std::size_t header_size)
    {
        tl::endpoint ep = req.get_endpoint();

        // Get the size of the bulk data
        std::size_t bulk_size = bulk.size();
        std::vector<char> buffer(bulk_size);

        std::vector<std::pair<void *, std::size_t>> segments(1);
        segments[0].first = buffer.data();
        segments[0].second = buffer.size();
        tl::bulk local = get_engine().expose(segments, tl::bulk_mode::write_only);
        bulk.on(ep) >> local;

        // Extract the header and data from the buffer
        std::string header(buffer.data(), header_size);
        std::vector<uint8_t> data(buffer.begin() + header_size, buffer.end());

        {
            std::lock_guard<tl::mutex> lock(mtx);
            Message msg;
            msg.header = header;
            msg.data = data;
            queue.push_back(msg);
        }
        cv.notify_one();
        req.respond();
    }

public:
    QueueProvider(tl::engine &engine, uint16_t provider_id = 1)
        : tl::provider<QueueProvider>(engine, provider_id)
    {
        define("push", &QueueProvider::push);
        define("push_rdma", &QueueProvider::push_rdma);
        std::cout << "QueueProvider initialized with provider ID " << provider_id << std::endl;
    }

    Message pull()
    {
        std::unique_lock<tl::mutex> lock(mtx);
        cv.wait(lock, [this]
                { return !queue.empty(); });
        Message msg = queue.front();
        queue.pop_front();
        return msg;
    }
};

#endif // QUEUE_PROVIDER_HPP