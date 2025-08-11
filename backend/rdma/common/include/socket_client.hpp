#pragma once
#include <iostream>
#include <string>
#include <vector>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>

namespace interactEM {

class SocketClient {
public:
    SocketClient(int port, const std::string& server_ip)
        : port_(port), server_ip_(server_ip), sock_(-1) {}

    ~SocketClient() {
        if (sock_ != -1) close(sock_);
    }

    bool connectToServer() {

        sock_ = socket(AF_INET, SOCK_STREAM, 0);
        if (sock_ < 0) return false;

        sockaddr_in serv_addr{};
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(port_);
        if (inet_pton(AF_INET, server_ip_.c_str(), &serv_addr.sin_addr) <= 0)
            return false;

        return connect(sock_, (sockaddr*)&serv_addr, sizeof(serv_addr)) == 0;
    }

    bool sendMessage(const std::string& msg) {
        return send(sock_, msg.c_str(), msg.size(), 0) == (ssize_t)msg.size();
    }

    std::string receiveMessage(size_t maxlen = 1024) {
        std::string result;
        std::vector<char> buffer(256);
        
        while (true) {
            int n = read(sock_, buffer.data(), buffer.size() - 1);
            if (n <= 0) break;
            
            buffer[n] = '\0';
            result += std::string(buffer.data(), n);
            
            // Check if we received a newline (end of message)
            if (result.find('\n') != std::string::npos) {
                break;
            }
            
            if (result.size() >= maxlen) break;
        }
        
        if (!result.empty() && result.back() == '\n') {
            result.pop_back();
        }
        
        return result;
    }

    bool isConnected() const {
        return sock_ != -1;
    }

private:
    std::string server_ip_;
    int port_;
    int sock_;
};

}