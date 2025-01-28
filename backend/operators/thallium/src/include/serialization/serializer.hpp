#ifndef SERIALIZER_HPP
#define SERIALIZER_HPP

#include "gen/message_generated.h"
#include <capnp/message.h>
#include <capnp/serialize.h>
#include <flatbuffers/flatbuffers.h>
#include <nanobind/ndarray.h>

#include <string>
#include <vector>

namespace nb = nanobind;

namespace interactEM {
namespace serialization {

class Serializer {
public:
  static std::pair<std::vector<char>, nb::ndarray<nb::numpy>>
  serialize(const std::string &header, nb::ndarray<nb::numpy> data) {
    flatbuffers::FlatBufferBuilder builder;

    // Create a vector for shape and strides
    std::vector<int64_t> shape(data.ndim());
    std::vector<int64_t> strides(data.ndim());
    for (size_t i = 0; i < data.ndim(); ++i) {
      shape[i] = data.shape(i);
      strides[i] = data.stride(i);
    }

    // Create DLTensor
    auto flat_shape = builder.CreateVector(shape);
    auto flat_strides = builder.CreateVector(strides);
    auto tensor = ThalliumQueue::Schemas::CreateDLTensor(
        builder, data.device_type(), data.device_id(),
        static_cast<int32_t>(data.ndim()),
        static_cast<int8_t>(data.dtype().bits),
        static_cast<int8_t>(data.dtype().code),
        static_cast<int16_t>(data.dtype().lanes), flat_shape, flat_strides,
        0 // This alignment doesn't matter for numpy, some discussion here:
          // https://github.com/data-apis/array-api/discussions/779
    );

    // Create DLTensorMessage
    auto message = ThalliumQueue::Schemas::CreateDLTensorMessage(
        builder, builder.CreateString(header), tensor);
    builder.Finish(message);

    // Serialize and return
    const uint8_t *buf = builder.GetBufferPointer();
    size_t size = builder.GetSize();
    return {std::vector<char>(buf, buf + size), data};
  }

  static std::pair<std::string, nb::ndarray<nb::numpy>>
  deserialize(const std::vector<char> &header_buffer,
              std::vector<char> &data_buffer) {
    // Deserialize FlatBuffers
    auto message =
        ThalliumQueue::Schemas::GetDLTensorMessage(header_buffer.data());
    std::string header = message->header()->str();

    auto tensor = message->tensor();
    nb::dlpack::dtype dtype;
    dtype.bits = tensor->dtype_bits();
    dtype.code = tensor->dtype_code();
    dtype.lanes = tensor->dtype_lanes();

    // Create shape
    std::vector<size_t> shape(tensor->shape()->size());
    for (size_t i = 0; i < shape.size(); ++i) {
      shape[i] = tensor->shape()->Get(i);
    }

    // Create strides
    std::vector<int64_t> strides(tensor->strides()->size());
    for (size_t i = 0; i < strides.size(); ++i) {
      strides[i] = tensor->strides()->Get(i);
    }

    nb::ndarray<nb::numpy> data(reinterpret_cast<void *>(data_buffer.data()),
                                tensor->ndim(), shape.data(), {},
                                strides.data(), dtype, tensor->device_type(),
                                tensor->device_id());

    return {header, data};
  }
};

} // namespace serialization
} // namespace interactEM

#endif // SERIALIZER_HPP