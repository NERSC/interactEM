#ifndef CAPNPROTO_SERIALIZER_HPP
#define CAPNPROTO_SERIALIZER_HPP

#include <capnp/message.h>
#include <nanobind/ndarray.h>
#include <string>
#include <vector>
#include <capnp/message.h>
#include <capnp/serialize.h>

#include "../proto/message.capnp.h"

namespace nb = nanobind;

namespace serialization
{

    class CapnProtoSerializer
    {
    public:
        // Serialize data into a Cap'n Proto message
        static std::pair<std::vector<char>, nb::ndarray<nb::numpy>> serialize(const std::string &header, nb::ndarray<nb::numpy> data)
        {
            // Initialize Cap'n Proto message
            ::capnp::MallocMessageBuilder builder;
            auto message = builder.initRoot<DLTensorMessage>();
            message.setHeader(header);

            // Initialize DLTensor
            DLTensor::Builder tensor = message.initTensor();
            tensor.setDeviceType(data.device_type());
            tensor.setDeviceId(data.device_id());
            tensor.setNdim(static_cast<int32_t>(data.ndim()));
            tensor.setDtypeBits(static_cast<int8_t>(data.dtype().bits));
            tensor.setDtypeCode(static_cast<int8_t>(data.dtype().code));
            tensor.setDtypeLanes(static_cast<int16_t>(data.dtype().lanes));

            auto shape = tensor.initShape(static_cast<unsigned int>(data.ndim()));
            for (size_t i = 0; i < data.ndim(); ++i)
            {
                shape.set(i, static_cast<int64_t>(data.shape(i)));
            }

            auto strides = tensor.initStrides(static_cast<unsigned int>(data.ndim()));
            for (size_t i = 0; i < data.ndim(); ++i)
            {
                strides.set(i, static_cast<int64_t>(data.stride(i)));
            }

            tensor.setByteOffset(0);
            auto serialized = ::capnp::messageToFlatArray(builder);
            auto serialized_encoded = serialized.asChars();

            std::vector<char> serialized_bytes(serialized_encoded.begin(), serialized_encoded.end());

            return {serialized_bytes, data}; // Return serialized bytes and the ndarray
        }

        // Deserialize CapProto message + data into a pair of header and ndarray
        static std::pair<std::string, nb::ndarray<nb::numpy>> deserialize(const std::vector<char> &header_buffer, std::vector<char> &data_buffer)
        {
            kj::ArrayPtr<capnp::word> header_array(reinterpret_cast<capnp::word *>(const_cast<char *>(header_buffer.data())), header_buffer.size() / sizeof(capnp::word));
            ::capnp::FlatArrayMessageReader messageReader(header_array);
            auto message = messageReader.getRoot<DLTensorMessage>();

            // Extract header
            auto header = message.getHeader().cStr();

            // Extract tensor information
            auto tensor = message.getTensor();

            nb::dlpack::dtype dtype;
            dtype.bits = tensor.getDtypeBits();
            dtype.code = tensor.getDtypeCode();
            dtype.lanes = tensor.getDtypeLanes();

            // Create a shape vector from tensor shape
            std::vector<size_t> shape;
            for (size_t s : tensor.getShape())
            {
                shape.emplace_back(s);
            }

            // Create a strides vector from tensor strides
            std::vector<int64_t> strides;
            for (int64_t stride : tensor.getStrides())
            {
                strides.emplace_back(stride);
            }

            nb::ndarray<nb::numpy> data(
                reinterpret_cast<void *>(data_buffer.data()), // void* pointer to the actual data
                tensor.getNdim(),                             // Number of dimensions
                shape.data(),                                 // Pointer to shape
                {},                                           // No owner
                strides.data(),                               // pointer to strides
                dtype,                                        // DLPack dtype
                tensor.getDeviceType(),                       // Device type
                tensor.getDeviceId()                          // Device ID
            );

            return {header, data};
        }
    };

} // namespace serialization

#endif // CAPNPROTO_SERIALIZER_HPP