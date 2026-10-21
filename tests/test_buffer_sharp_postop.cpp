// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <cassert>
#include <cstring>
#include "shader_recompiler/resource.h"

int main() {
    struct Info {
        std::array<u32, 4> flattened_ud_buf{};
        u64 pgm_base{};
    } info;
    AmdGpu::Buffer original{};
    original.base_address = 0x123456780ULL;
    original.stride = 16;
    original.num_records = 17;
    original.dst_sel_x = 4;
    original.cache_swizzle = 1;
    original.swizzle_enable = 1;
    std::memcpy(info.flattened_ud_buf.data(), &original, sizeof(original));

    Shader::BufferResource resource{};
    resource.sharp_fetch.summary = Shader::SharpFetch<AmdGpu::Buffer>::Summary::SingleLoad;
    resource.sharp_fetch.offsets[0] = 0;
    resource.post_op = Shader::SharpFetchPostOp::ClearStrideAndBitshiftDw2WithImm;
    resource.post_op_dw2_shift = 4;
    auto result = resource.GetSharp(info);
    assert(result.stride == 0 && result.num_records == 272);
    assert(result.base_address == original.base_address);
    assert(result.cache_swizzle == original.cache_swizzle);
    assert(result.swizzle_enable == original.swizzle_enable);
    assert(result.dst_sel_x == original.dst_sel_x);
    assert(info.flattened_ud_buf[2] == 17); // fetching must not modify source descriptors

    resource.sharp_fetch.summary = Shader::SharpFetch<AmdGpu::Buffer>::Summary::MultiLoad;
    resource.sharp_fetch.load_mask = 0;
    std::memcpy(resource.sharp_fetch.immediates.data(), &original, sizeof(original));
    assert(resource.GetSharp(info) == result); // immediate and flat-buffer paths agree
    resource.post_op_dw2_shift = 0;
    result = resource.GetSharp(info);
    assert(result.stride == 0 && result.num_records == 17);
    resource.post_op = Shader::SharpFetchPostOp::None;
    assert(resource.GetSharp(info) == original);
    resource.sharp_fetch.summary = Shader::SharpFetch<AmdGpu::Buffer>::Summary::Invalid;
    assert(resource.GetSharp(info) == AmdGpu::Buffer::Null());
}
