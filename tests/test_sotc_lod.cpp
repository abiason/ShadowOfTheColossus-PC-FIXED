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
constexpr uintptr_t LargeBitmap = 0x1000200000;
std::array<u8, 0x68> pool{};
std::array<u64, 2> bitmap{};
std::array<u64, 16> alternate{};
std::array<u64, 1024> large_bitmap{};
size_t large_mapped_words = large_bitmap.size();
bool mapped = true;
bool split = false;
bool hole = false, fragmented = false, remapped_middle = false;
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
        const auto offset = address - Bitmap;
        if (hole && offset >= 4 && offset < 12) return nullptr;
        if (fragmented && offset >= 8) {
            return reinterpret_cast<const u8*>(alternate.data() + 8) + offset - 8;
        }
        if (remapped_middle && offset >= 4 && offset < 12) {
            return reinterpret_cast<const u8*>(alternate.data() + 8) + offset - 4;
        }
        if (split && address != Bitmap) return nullptr;
        return reinterpret_cast<const u8*>(bitmap.data()) + (address - Bitmap);
    }
    if (address >= LargeBitmap && address - LargeBitmap < large_mapped_words * 8) {
        return reinterpret_cast<const u8*>(large_bitmap.data()) + (address - LargeBitmap);
    }
    return nullptr;
}

extern "C" int runtime_memory_region(uintptr_t address, uintptr_t* lo, uintptr_t* hi, int* valid) {
    *valid = mapped;
    if (address >= Pool && address - Pool < pool.size()) {
        *lo = Pool; *hi = Pool + pool.size();
        return 1;
    }
    if (address >= Bitmap && address - Bitmap < sizeof(bitmap)) {
        const auto offset = address - Bitmap;
        *lo = Bitmap; *hi = Bitmap + sizeof(bitmap);
        if (split) { *hi = Bitmap + 1; *valid = mapped && offset == 0; }
        if (hole || remapped_middle) {
            *lo = Bitmap + (offset < 4 ? 0 : offset < 12 ? 4 : 12);
            *hi = Bitmap + (offset < 4 ? 4 : offset < 12 ? 12 : sizeof(bitmap));
            if (hole && offset >= 4 && offset < 12) *valid = 0;
        } else if (fragmented) {
            *lo = Bitmap + (offset < 8 ? 0 : 8);
            *hi = Bitmap + (offset < 8 ? 8 : sizeof(bitmap));
        }
        return 1;
    }
    if (address >= LargeBitmap && address - LargeBitmap < sizeof(large_bitmap)) {
        *lo = LargeBitmap; *hi = LargeBitmap + large_mapped_words * 8;
        *valid = mapped && address < *hi;
        return 1;
    }
    *valid = 0;
    return 0;
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
    if (mode == "priority") {
        u64 entries[256]{};
        SotcLod::uses[7].store(1);
        SotcLod::Collect(entries);
        assert(((entries[7] >> 32) & 0xffffff) == 256);
        for (u32 count : {0x10000u, 0x1000000u}) {
            SotcLod::uses[7].store(count);
            SotcLod::Collect(entries);
            assert(((entries[7] >> 32) & 0xffffff) == 0xffffff);
        }
        std::puts("SotC LOD: sample priority saturates without integer wrap");
        return 0;
    }
    if (mode == "mapping") {
        // The first and last bytes remain valid and physically contiguous, but
        // the middle guest mapping is absent. Endpoint-only validation misses it.
        hole = true;
        assert(SotcLod::PoolFreePercent() == -1);
        hole = false;
        alternate[8] = ~u64{0};
        remapped_middle = true;
        assert(SotcLod::PoolFreePercent() == 64); // Middle bytes come from a different backing.
        remapped_middle = false;
        bitmap[0] = 0x3ff;
        alternate[8] = 0x3ff;
        fragmented = true;
        assert(SotcLod::PoolFreePercent() == 20);
        fragmented = false;
        field(0x50, LargeBitmap);
        field(0x58, 513);
        field(0x60, 512 * 64 + 5);
        large_bitmap.fill(~u64{0});
        assert(SotcLod::PoolFreePercent() == 100); // A second chunk with a partial final word.
        large_mapped_words = 512;
        assert(SotcLod::PoolFreePercent() == -1); // Missing second chunk is not a partial success.
        std::puts("SotC LOD: guest mapping holes and physical remaps passed");
        return 0;
    }
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
