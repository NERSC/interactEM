@0xdccfaa984656effe;

struct DLTensor {
  deviceType @0 :Int32; # Device type
  deviceId @1 :Int32; # Device ID
  ndim @2 :Int32; # Number of dimensions
  dtypeBits @3 :Int8; # Data type bits
  dtypeCode @4 :Int8; # Data type code
  dtypeLanes @5 :Int16; # Number of lanes in the data type
  shape @6 :List(Int64); # Shape of the array
  strides @7 :List(Int64); # Strides of the array
  byteOffset @8 :Int64; # Byte offset
}

struct DLTensorMessage {
  header @0 :Text;
  tensor @1 :DLTensor;
}