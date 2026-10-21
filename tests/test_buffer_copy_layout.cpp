// SPDX-License-Identifier: GPL-2.0-or-later
#include <cassert>
#include "video_core/renderer_vulkan/buffer_copy_layout.h"

int main() {
    using Vulkan::BuildBufferCopyLayout;
    constexpr auto color = vk::ImageAspectFlagBits::eColor;
    constexpr auto r32 = vk::Format::eR32Sfloat;
    const auto single = BuildBufferCopyLayout({1920, 1080, 1}, 1, 1, color, r32, r32);
    assert(single.size == 8294400 && single.regions.size() == 1);

    // Odd dimensions, two array layers, alignment gaps, and a one-texel tail.
    auto array = BuildBufferCopyLayout({7, 5, 1}, 3, 2, color, r32, r32);
    assert(array.size == 344 && array.regions.size() == 3);
    assert(array.regions[1].bufferOffset == 288);
    assert(array.regions[1].imageExtent == vk::Extent3D(3, 2, 1));
    assert(array.regions[2].bufferOffset == 336);
    assert(array.regions[2].imageSubresource.layerCount == 2);
    assert(array.regions[2].imageSubresource.mipLevel == 2);
    // Staging allocations can start at a nonzero base; relative span stays unchanged.
    for (auto& region : array.regions) region.bufferOffset += 256;
    assert(array.regions[1].bufferOffset == 544);
    assert(array.regions[2].bufferOffset + 8 == 256 + array.size);

    // Full-format sizes conservatively reserve enough space for either depth format.
    const auto depth = BuildBufferCopyLayout({7, 5, 1}, 3, 2,
        vk::ImageAspectFlagBits::eDepth, vk::Format::eD32Sfloat, vk::Format::eD32SfloatS8Uint);
    const auto reverse = BuildBufferCopyLayout({7, 5, 1}, 3, 2,
        vk::ImageAspectFlagBits::eDepth, vk::Format::eD32SfloatS8Uint, vk::Format::eD32Sfloat);
    assert(depth.size == 426 && reverse.size == depth.size);
    assert(depth.regions[1].bufferOffset == 352);
    assert(depth.regions[2].bufferOffset == 416);

    const auto compressed = BuildBufferCopyLayout({7, 5, 1}, 3, 1, color,
        vk::Format::eBc1RgbaUnormBlock, vk::Format::eBc1RgbaUnormBlock);
    assert(compressed.size == 56);
    assert(compressed.regions[1].bufferOffset == 32);
    assert(compressed.regions[2].bufferOffset == 48);

    const auto volume = BuildBufferCopyLayout({7, 5, 5}, 3, 1, color,
        vk::Format::eR8Unorm, vk::Format::eR8Unorm);
    assert(volume.size == 193);
    assert(volume.regions[1].imageExtent == vk::Extent3D(3, 2, 2));
    assert(volume.regions[2].imageExtent == vk::Extent3D(1, 1, 1));

    const auto large = BuildBufferCopyLayout({65536, 65536, 1}, 1, 1, color, r32, r32);
    assert(large.size == 17179869184ULL); // sizing must not wrap at 4 GiB
}
