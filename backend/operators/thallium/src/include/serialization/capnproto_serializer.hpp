#ifndef SERIALIZER_HPP
#define SERIALIZER_HPP

#include "../proto/message.capnp.h"
#include "gen/message_generated.h"
#include <capnp/message.h>
#include <capnp/serialize.h>
#include <flatbuffers/flatbuffers.h>
#include <nanobind/ndarray.h>

#include <string>
#include <vector>

namespace nb = nanobind;

namespace serialization {

enum class SerializationType { CapnProto, FlatBuffers };

class Serializer {
public:
  static std::pair<std::vector<char>, nb::ndarray<nb::numpy>>
  serialize(SerializationType type, const std::string &header,
            nb::ndarray<nb::numpy> data) {
    if (type == SerializationType::CapnProto) {
      return serializeCapnProto(header, data);
    } else {
      return serializeFlatBuffers(header, data);
    }
  }

  static std::pair<std::string, nb::ndarray<nb::numpy>>
  deserialize(SerializationType type, const std::vector<char> &header_buffer,
              std::vector<char> &data_buffer) {
    if (type == SerializationType::CapnProto) {
      return deserializeCapnProto(header_buffer, data_buffer);
    } else {
      return deserializeFlatBuffers(header_buffer, data_buffer);
    }
  }

private:
  static std::pair<std::vector<char>, nb::ndarray<nb::numpy>>
  serializeCapnProto(const std::string &header, nb::ndarray<nb::numpy> data) {
    // Implementation of Cap'n Proto serialization (existing code)
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
    for (size_t i = 0; i < data.ndim(); ++i) {
      shape.set(i, static_cast<int64_t>(data.shape(i)));
    }

    auto strides = tensor.initStrides(static_cast<unsigned int>(data.ndim()));
    for (size_t i = 0; i < data.ndim(); ++i) {
      strides.set(i, static_cast<int64_t>(data.stride(i)));
    }

    tensor.setByteOffset(0);
    auto serialized = ::capnp::messageToFlatArray(builder);
    auto serialized_encoded = serialized.asChars();

    std::vector<char> serialized_bytes(serialized_encoded.begin(),
                                       serialized_encoded.end());
    return {serialized_bytes, data};
  }

  static std::pair<std::string, nb::ndarray<nb::numpy>>
  deserializeCapnProto(const std::vector<char> &header_buffer,
                       std::vector<char> &data_buffer) {
    kj::ArrayPtr<capnp::word> header_array(
        reinterpret_cast<capnp::word *>(
            const_cast<char *>(header_buffer.data())),
        header_buffer.size() / sizeof(capnp::word));
    ::capnp::FlatArrayMessageReader messageReader(header_array);
    auto message = messageReader.getRoot<DLTensorMessage>();

    auto header = message.getHeader().cStr();
    auto tensor = message.getTensor();

    nb::dlpack::dtype dtype;
    dtype.bits = tensor.getDtypeBits();
    dtype.code = tensor.getDtypeCode();
    dtype.lanes = tensor.getDtypeLanes();

    // Create shape
    std::vector<size_t> shape;
    for (size_t s : tensor.getShape()) {
      shape.emplace_back(s);
    }

    // Create strides
    std::vector<int64_t> strides;
    for (int64_t stride : tensor.getStrides()) {
      strides.emplace_back(stride);
    }

    nb::ndarray<nb::numpy> data(reinterpret_cast<void *>(data_buffer.data()),
                                tensor.getNdim(), shape.data(), {},
                                strides.data(), dtype, tensor.getDeviceType(),
                                tensor.getDeviceId());

    return {header, data};
  }

  static std::pair<std::vector<char>, nb::ndarray<nb::numpy>>
  serializeFlatBuffers(const std::string &header, nb::ndarray<nb::numpy> data) {
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
        0 // Assuming byte offset is 0 for now
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
  deserializeFlatBuffers(const std::vector<char> &header_buffer,
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

#endif // SERIALIZER_HPP