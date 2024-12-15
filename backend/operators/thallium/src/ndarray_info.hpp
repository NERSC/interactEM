#ifndef MESSAGE_INFO_HPP
#define MESSAGE_INFO_HPP

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include <iostream>

namespace nb = nanobind;

void print_ndarray_info(const nb::ndarray<nb::numpy> &data) {
  if (!data.is_valid()) {
    std::cout << "ndarray is not valid." << std::endl;
    return;
  }

  std::cout << "ndarray Info:" << std::endl;

  std::cout << "  Number of dimensions: " << data.ndim() << std::endl;
  std::cout << "  Shape: ";
  for (size_t i = 0; i < data.ndim(); ++i) {
    std::cout << data.shape(i) << " ";
  }
  std::cout << std::endl;

  std::cout << "  Strides: ";
  for (size_t i = 0; i < data.ndim(); ++i) {
    std::cout << data.stride(i) << " ";
  }
  std::cout << std::endl;

  std::cout << "  Data type bits: " << data.dtype().bits << std::endl;
  std::cout << "  Data type code: " << data.dtype().code << std::endl;
  std::cout << "  Data type lanes: " << data.dtype().lanes << std::endl;
  std::cout << "  Item size: " << data.itemsize() << " bytes" << std::endl;
  std::cout << "  Total bytes: " << data.nbytes() << " bytes" << std::endl;
  std::cout << "  Total elements: " << data.size() << std::endl;
  std::cout << "  Data pointer: " << data.data()
            << std::endl; // Address of the data
}

#endif