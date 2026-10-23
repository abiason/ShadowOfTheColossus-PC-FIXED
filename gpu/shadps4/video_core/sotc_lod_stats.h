// SPDX-License-Identifier: GPL-2.0-or-later
// sotc: texture LOD statistics (PM4 GET_LOD_STATS). A T# with LOD_HW_CNT_EN counts, in its
// counter bank (COUNTER_BANK_ID, 256 banks), how its texture was sampled; GET_LOD_STATS writes
// the banks to memory. Shadow of the Colossus streams the fine mips of its textures from these
// numbers: without them it never loads more than the 256x256 mip (blurry ground and rocks,
// black water, missing waterfall sheets). The port marks the banks of the T#s bound by draws
// and dispatches; GET_LOD_STATS reports a bank marked in the last reports as sampled (the
// hardware accumulates over many frames too: a texture missing from one frame must not read as
// unused, or the game drops mips it is still loading).
// The hardware knows the LOD each texture is sampled at; the port does not, so every sampled
// bank asks for the same mip. Asking for mip 0 everywhere fills the game's streaming pool and
// the game then breaks guest memory (heap and descriptor corruption within 1-4 minutes of the
// attract demo, also with mip 1); mip 2 (512x512 for the 2048 textures, 4x the old 256x256)
// ran the whole demo, but loading a save in the waterfall area then broke it too (3 of 4 runs,
// 2026-10-13) until the GPU readback on unmap was dropped (Rasterizer::UnmapMemory); mip 2 then
// ran 25+ minutes there. SOTC_LOD_LEVEL picks another mip for tests.
#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iterator>
#include "common/types.h"

extern "C" const unsigned char* runtime_memory_backing_pointer(uintptr_t address);
extern "C" int runtime_memory_region(uintptr_t address, uintptr_t* start, uintptr_t* end,
                                     int* mapped);

namespace SotcLod {

inline std::atomic<u32> uses[256]{};

inline bool ReadBacking(uintptr_t address, void* destination, u64 size) {
    if (!size || address > UINTPTR_MAX - (size - 1)) {
        return false;
    }
    auto* out = static_cast<u8*>(destination);
    while (size) {
        uintptr_t start = 0, end = 0;
        int mapped = 0;
        if (!runtime_memory_region(address, &start, &end, &mapped) || !mapped ||
            address < start || address >= end) {
            return false;
        }
        const u8* backing = runtime_memory_backing_pointer(address);
        if (!backing) {
            return false;
        }
        const u64 count = std::min<u64>(size, end - address);
        std::memcpy(out, backing, count);
        address += count;
        out += count;
        size -= count;
    }
    return true;
}

// EU 1.01's 64 KiB streaming-page pool. Read its bitmap through the backing view,
// bypassing GPU tracking protection. An unavailable or invalid pool must not change LOD.
// Adapted from AjncSystem's 0.60.3/0.60.4 pressure protection, PR #191.
inline int PoolFreePercent() {
    constexpr uintptr_t Pool = 0x1000000140;
    std::array<u8, 0x68> pool;
    if (!ReadBacking(Pool, pool.data(), pool.size())) {
        return -1;
    }
    u64 bitmap, words, pages;
    std::memcpy(&bitmap, pool.data() + 0x50, 8);
    std::memcpy(&words, pool.data() + 0x58, 8);
    std::memcpy(&pages, pool.data() + 0x60, 8);
    if (!words || words > 0x10000 || !pages || pages > words * 64) {
        return -1;
    }
    const u64 needed = (pages + 63) / 64;
    if (bitmap > UINTPTR_MAX - (needed * 8 - 1)) {
        return -1;
    }
    u64 free = 0;
    for (u64 offset = 0; offset < needed;) {
        std::array<u64, 512> chunk;
        const u64 count = std::min<u64>(chunk.size(), needed - offset);
        if (!ReadBacking(bitmap + offset * 8, chunk.data(), count * 8)) {
            return -1; // Never report a partial count as a valid pool percentage.
        }
        for (u64 i = 0; i < count; ++i) {
            u64 word = chunk[i];
            if (const u64 remaining = pages - (offset + i) * 64; remaining < 64) {
                word &= (u64{1} << remaining) - 1;
            }
            free += std::popcount(word);
        }
        offset += count;
    }
    return static_cast<int>(free * 100 / pages);
}
/// Reports a bank stays sampled after its last use. 0, like Pink-shadPS4: only the banks used
/// since the last report. 180 (about 3 s) made the game ask for more than its streaming pool holds
/// (allocator fault at guest 0x1a371 in 1 of 3 runs of the attract demo; 0 of 5 without).
constexpr u32 Linger = 0;

inline void Mark(u32 bank) {
    uses[bank & 0xff].fetch_add(1, std::memory_order_relaxed);
}

/// The 256 bank entries the game reads (u64 each): bits 56-59 the finest mip sampled (15: not
/// sampled), bits 32-55 how much (the game's streaming priority). Called once per report.
inline void Collect(u64 (&entries)[256]) {
    // SOTC_LOD_LINGER=<reports>: how long a bank stays sampled (test knob).
    static const u32 linger = [] {
        const char* v = std::getenv("SOTC_LOD_LINGER");
        return v ? static_cast<u32>(std::strtoul(v, nullptr, 0)) : Linger;
    }();
    // SOTC_LOD_LEVEL=<mip>: the finest mip reported for a sampled bank. Default 2: mip 0 (Pink-
    // shadPS4) filled an 8 GB card and stalled the GPU after a save loaded; mip 3 made the game
    // evict mips the GPU still sampled (garbage grass).
    static const u64 level = [] {
        const char* v = std::getenv("SOTC_LOD_LEVEL");
        return v ? std::strtoull(v, nullptr, 0) & 0xf : 2;
    }();
    static const int pool_low = [] {
        const char* v = std::getenv("SOTC_LOD_POOL_LOW");
        return v ? std::clamp(std::atoi(v), 0, 100) : 8;
    }();
    static u64 coarser = 0;
    static u32 reports = 0;
    if (linger && pool_low > 0 && reports++ % 30 == 0) {
        const int free = PoolFreePercent();
        u64 want = coarser;
        if (free >= 0) {
            if (free < pool_low * 3 / 8) {
                want = 2;
            } else if (free < pool_low) {
                want = std::max<u64>(coarser, 1);
            } else if (coarser == 2 && free > pool_low * 3 / 4) {
                want = 1;
            }
            // Hysteresis from 0.60.4: only return to the finest mip above 16% free.
            if (want == 1 && coarser == 1 && free > pool_low * 2) {
                want = 0;
            }
        }
        if (want != coarser) {
            coarser = want;
            std::fprintf(stderr, "SOTC LOD: game page pool %d%% free, sampled textures ask for mip %u\n",
                         free, static_cast<unsigned>(std::min<u64>(level + coarser, 14)));
        }
    }
    const u64 mip = std::min<u64>(level + coarser, 14);
    static u32 idle[256] = {}; // reports since the bank's last use (never used: all ones)
    static const bool idle_ready = [] {
        std::fill(std::begin(idle), std::end(idle), 0xffffffffu);
        return true;
    }();
    (void)idle_ready;
    static u32 last_count[256]{};
    for (u32 i = 0; i < 256; ++i) {
        const u32 n = uses[i].exchange(0, std::memory_order_relaxed);
        if (n) {
            idle[i] = 0;
            last_count[i] = static_cast<u32>(std::min<u64>(u64{n} * 256, 0xffffff));
        } else if (idle[i] < linger) {
            ++idle[i];
        }
        // Banks not seen lately read as not sampled (15), as on the hardware: the game may then
        // drop their fine mips. SOTC_LOD_KEEP=1 reports them as sampled with no samples instead
        // (what the zeroed buffer said before; not soak-tested with the streaming).
        static const bool keep = std::getenv("SOTC_LOD_KEEP") != nullptr;
        entries[i] = idle[i] < linger ? (mip << 56) | (u64{std::max<u32>(last_count[i], 1)} << 32)
                     : keep           ? level << 56
                                      : u64{0xf} << 56;
    }
}

} // namespace SotcLod
