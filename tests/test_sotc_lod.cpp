// SPDX-License-Identifier: GPL-2.0-or-later
// Exercise the real streaming reports with a synthetic guest page pool.
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string_view>
#include "video_core/sotc_lod_stats.h"

namespace {
constexpr uintptr_t Pool = 0x1000000140;
constexpr uintptr_t Bitmap = 0x1000100000;
std::array<u8, 0x68> pool{};
std::array<u64, 2> bitmap{};
bool mapped = true;
bool split = false;
void field(size_t offset, u64 value) { std::memcpy(pool.data() + offset, &value, 8); }
void free_pages(unsigned count) {
    bitmap.fill(0);
    for (unsigned i = 0; i < count; ++i) bitmap[i / 64] |= u64{1} << (i % 64);
}
u64 report(unsigned count = 1) {
    u64 entries[256]{};
    for (unsigned i = 0; i < count; ++i) {
        SotcLod::Mark(7);
        SotcLod::Collect(entries);
    }
    assert((entries[3] >> 56) == 15); // Never sampled, even under pressure.
    return entries[7] >> 56;
}
}

extern "C" const unsigned char* runtime_memory_backing_pointer(uintptr_t address) {
    if (!mapped) return nullptr;
    if (address >= Pool && address - Pool < pool.size()) return pool.data() + (address - Pool);
    if (address >= Bitmap && address - Bitmap < sizeof(bitmap)) {
        if (split && address != Bitmap) return nullptr;
        return reinterpret_cast<const u8*>(bitmap.data()) + (address - Bitmap);
    }
    return nullptr;
}

int main(int argc, char** argv) {
    field(0x50, Bitmap);
    field(0x58, 2);
    field(0x60, 100);
    free_pages(50);
    assert(SotcLod::PoolFreePercent() == 50);
    // Padding bits outside the page count must not inflate the free share.
    bitmap[1] = ~u64{0} << 36;
    bitmap[0] = 0;
    assert(SotcLod::PoolFreePercent() == 0);
    mapped = false;
    assert(SotcLod::PoolFreePercent() == -1);
    mapped = true;
    split = true;
    assert(SotcLod::PoolFreePercent() == -1);
    split = false;
    for (const u64 words : {0ULL, 0x10001ULL}) {
        field(0x58, words);
        assert(SotcLod::PoolFreePercent() == -1);
    }
    field(0x58, 2);
    for (const u64 pages : {0ULL, 129ULL}) {
        field(0x60, pages);
        assert(SotcLod::PoolFreePercent() == -1);
    }
    field(0x60, 100);
    field(0x50, UINTPTR_MAX - 3);
    assert(SotcLod::PoolFreePercent() == -1);
    field(0x50, Bitmap);

    const std::string_view mode = argc > 1 ? argv[1] : "pressure";
    free_pages(0);
    if (mode == "disabled") {
        assert(report() == 2);
    } else if (mode == "off") {
        assert(report() == 15); // No high-quality texture reports when linger is zero.
    } else if (mode == "clamped") {
        assert(report() == 14); // Level + pressure cannot become the 'not sampled' marker.
    } else {
        assert(report() == 4); // Empty pool: request two coarser mips immediately.
        free_pages(5);
        assert(report(30) == 4); // Do not oscillate near the critical threshold.
        free_pages(9);
        assert(report(30) == 3);
        free_pages(16);
        assert(report(30) == 3); // Recovery requires strictly more than 16%.
        free_pages(17);
        assert(report(30) == 2);
        free_pages(7);
        assert(report(30) == 3);
        free_pages(12);
        assert(report(30) == 3); // Hysteresis keeps coarse LOD between 8 and 16%.
        mapped = false;
        assert(report(30) == 3); // A loading/unmapping pool must not force recovery.
    }
    std::puts("SotC LOD: pool validation and streaming reports passed");
}
