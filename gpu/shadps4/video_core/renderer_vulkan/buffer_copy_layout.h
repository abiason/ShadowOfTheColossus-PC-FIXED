// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <cstdint>
#include <boost/container/small_vector.hpp>
#include "video_core/renderer_vulkan/vk_common.h"
#include <vulkan/vulkan_format_traits.hpp>

namespace Vulkan {

struct BufferCopyLayout {
    boost::container::small_vector<vk::BufferImageCopy, 8> regions;
    std::uint64_t size{};
};

// Relative offsets, shared by allocation and command emission. Reserve enough space for
// either format (depth/stencil aspects can occupy less space than the complete format).
inline BufferCopyLayout BuildBufferCopyLayout(vk::Extent3D extent, std::uint32_t levels,
                                              std::uint32_t layers,
                                              vk::ImageAspectFlags source_aspect,
                                              vk::Format source, vk::Format destination) {
    BufferCopyLayout layout;
    const auto level_size = [layers](vk::Extent3D size, vk::Format format) {
        const auto block = vk::blockExtent(format);
        const auto width = (std::uint64_t{size.width} + block[0] - 1) / block[0];
        const auto height = (std::uint64_t{size.height} + block[1] - 1) / block[1];
        const auto depth = (std::uint64_t{size.depth} + block[2] - 1) / block[2];
        return width * height * depth * layers * vk::blockSize(format);
    };
    for (std::uint32_t mip = 0; mip < levels; ++mip) {
        const std::uint64_t offset = (layout.size + 15) & ~std::uint64_t{15};
        layout.regions.push_back(vk::BufferImageCopy{
            .bufferOffset = offset,
            .imageSubresource{.aspectMask = source_aspect,
                              .mipLevel = mip,
                              .baseArrayLayer = 0,
                              .layerCount = layers},
            .imageExtent = extent,
        });
        layout.size = offset + std::max(level_size(extent, source),
                                       level_size(extent, destination));
        extent = vk::Extent3D{std::max(extent.width / 2, 1u),
                              std::max(extent.height / 2, 1u),
                              std::max(extent.depth / 2, 1u)};
    }
    return layout;
}

} // namespace Vulkan
