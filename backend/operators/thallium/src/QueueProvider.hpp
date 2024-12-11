#ifndef QUEUE_PROVIDER_HPP
#define QUEUE_PROVIDER_HPP

#include <thallium.hpp>
#include <deque>
#include <string>
#include <thallium/serialization/stl/string.hpp>
#include <chrono>
#include <vector>

namespace tl = thallium;

class QueueProvider : public tl::provider<QueueProvider>
{
private:
    std::deque<std::string> queue;
    tl::mutex mtx;
    tl::condition_variable cv;

    int push(const std::string &message)
    {
        {
            std::lock_guard<tl::mutex> lock(mtx);
            queue.push_back(message);
        }
        cv.notify_one();
        return 42;
    }

    void push_rdma(const tl::request &req, tl::bulk &bulk)
    {
        tl::endpoint ep = req.get_endpoint();

        std::size_t bulk_size = bulk.size();
        std::vector<char> buffer(bulk_size);

        std::vector<std::pair<void *, std::size_t>> segments(1);
        segments[0].first = buffer.data();
        segments[0].second = buffer.size();
        tl::bulk local = get_engine().expose(segments, tl::bulk_mode::write_only);
        bulk.on(ep) >> local;

        std::string message(buffer.data(), bulk_size);
        {
            std::lock_guard<tl::mutex> lock(mtx);
            queue.push_back(message);
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

    std::string pull()
    {
        std::unique_lock<tl::mutex> lock(mtx);
        cv.wait(lock, [this]
                { return !queue.empty(); });
        std::string message = queue.front();
        queue.pop_front();
        return message;
    }
};

#endif // QUEUE_PROVIDER_HPP