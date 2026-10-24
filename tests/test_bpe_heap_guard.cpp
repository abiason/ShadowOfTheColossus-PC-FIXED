// SPDX-License-Identifier: GPL-2.0-or-later
#include "core/memory.h"
#include "video_core/buffer_cache/bpe_heap_guard.h"
#include <array>
#include <cassert>
#include <cstring>
#include <iostream>

namespace {
constexpr VAddr Heap = 0x10000000, Base = 0x100000000;
std::array<u8, 0x1000> heap;
std::array<u8, 0x10000> region;
size_t writes, reads;
u8* backing(VAddr addr, u64 size) {
    if (addr >= Heap && addr - Heap < heap.size() && size <= heap.size() - (addr - Heap))
        return heap.data() + addr - Heap;
    if (addr >= Base && addr - Base < region.size() && size <= region.size() - (addr - Base))
        return region.data() + addr - Base;
    return nullptr;
}
void put(VAddr addr, u64 value) { auto p = backing(addr, 8); assert(p); std::memcpy(p, &value, 8); }
u64 get(VAddr addr) { u64 value; auto p = backing(addr, 8); assert(p); std::memcpy(&value, p, 8); return value; }
void reset() {
    heap.fill(0); region.fill(0); writes = 0;
    put(Heap + 0x80, Heap + 0x80);
    put(Base, 0); put(Base + 8, 3);
    put(Base + 16, Base); put(Base + 24, region.size() - 48 + 1);
    put(Base + region.size() - 16, Base + 16); put(Base + region.size() - 8, 1);
}
}
namespace Core {
u64 MemoryManager::ClampRangeSize(VAddr addr, u64 size) { return backing(addr, size) ? size : 0; }
const u8* MemoryManager::GetBackingRun(VAddr addr, VAddr* start, u64* size) const {
    if (backing(addr, 1)) { *start = addr >= Base ? Base : Heap; *size = addr >= Base ? region.size() : heap.size(); return backing(*start, *size); }
    return nullptr;
}
bool MemoryManager::TryCopySparseMemory(VAddr addr, u8* out, u64 size) {
    ++reads; auto p = backing(addr, size); if (!p) return false; std::memcpy(out, p, size); return true;
}
bool MemoryManager::TryWriteBacking(void* addr, const void* data, u64 size, u32) {
    auto p = backing(reinterpret_cast<VAddr>(addr), size); if (!p) return false;
    ++writes; std::memcpy(p, data, size); return true;
}
}
int main() {
    Core::MemoryManager instance;
    auto memory = &instance;
    const std::array<VideoCore::BpeHeapGuard::Region, 1> regions{{{Base, region.size()}}};
    std::array<u8, 0x10000> gpu; gpu.fill(0xa5);
    reset();
    VideoCore::BpeHeapGuard guard{memory, Heap, regions};
    assert(guard.IsValid());
    u64 kept = 0;
    assert(guard.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(kept == 48 && writes == 1);
    assert(get(Base + 8) == 3 && get(Base + 24) == region.size() - 48 + 1);
    assert(region[32] == 0xa5 && get(Base + region.size() - 8) == 1);
    // Same guard object must re-read allocator state; no stale tree/signature cache.
    reset();
    put(Heap + 0x80, Base + 32);
    put(Base + 24, region.size() - 48); // now a free block
    put(Base + 32, Heap + 0x80); put(Base + 40, Heap + 0x80); put(Base + 48, Base + 32);
    assert(guard.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(kept == 88 && get(Base + 32) == Heap + 0x80 && region[72] == 0xa5);
    reset();
    put(Heap + 0x80, Base + 32); put(Base + 24, region.size() - 48);
    put(Base + 32, 0); put(Base + 40, 0); put(Base + 48, Base + 32);
    assert(guard.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(kept == 88 && get(Base + 32) == 0); // Equal-key nodes have null children.
    reset();
    put(Base + 24, region.size() - 48 + 5); // allocated + trailing debug id
    const u32 debug_id = 0x12345678;
    std::memcpy(region.data() + region.size() - 20, &debug_id, sizeof(debug_id));
    assert(guard.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(kept == 52);
    assert(std::memcmp(region.data() + region.size() - 20, &debug_id, sizeof(debug_id)) == 0);
    reset();
    put(Base + region.size() - 16, Base + 24); // inconsistent physical chain
    assert(!guard.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(writes == 0 && std::strcmp(guard.LastFailure(), "physical-chain-invalid") == 0);
    reset();
    VideoCore::BpeHeapGuard bad_tree{memory, Heap, regions};
    put(Heap + 0x80, Base + region.size() + 16);
    assert(bad_tree.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(kept == 48); // Free-tree pointers are irrelevant to physical metadata ownership.
    // Legitimate equal-size rings may exceed the old 1024-peer limit.
    reset(); reads = 0;
    constexpr size_t peers = 1026, stride = 56;
    const VAddr first = Base + 16;
    for (size_t i = 0; i < peers; ++i) {
        const VAddr block = first + i * stride;
        put(block, i ? block - stride : Base); put(block + 8, 40);
        put(block + 16, 0); put(block + 24, 0);
        put(block + 32, first + ((i + 1) % peers) * stride + 16);
    }
    const VAddr tail = first + peers * stride;
    put(tail, tail - stride); put(tail + 8, Base + region.size() - tail - 32 + 1);
    put(Base + region.size() - 16, tail); put(Heap + 0x80, first + 16);
    VideoCore::BpeHeapGuard batch{memory, Heap, regions};
    batch.UseLockedBatch();
    assert(batch.TryWrite(Base, gpu.data(), gpu.size(), kept));
    const size_t first_reads = reads;
    assert(kept == peers * stride + 48 && region[tail - Base + 16] == 0xa5);
    assert(batch.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(reads - first_reads < first_reads * 2 / 3); // Reuse only inside one held-lock batch.
    put(first + stride + 32, first + stride + 16); // Peer cycle does not close at the root.
    writes = 0;
    VideoCore::BpeHeapGuard cycle{memory, Heap, regions};
    assert(cycle.TryWrite(Base, gpu.data(), gpu.size(), kept));
    assert(kept == peers * stride + 48);
    assert(get(first + stride + 32) == first + stride + 16); // Preserve, never follow, peer links.
    reset();
    put(Base+8,region.size()+3); // Cached empty reserve stores its full size here.
    VideoCore::BpeHeapGuard cached{memory,Heap,regions,nullptr,nullptr,regions};
    assert(cached.TryWrite(Base,gpu.data(),gpu.size(),kept));
    assert(kept==16 && get(Base+8)==region.size()+3 && region[16]==0xa5);
    reset(); put(Base+8,0x20003); writes=0;
    VideoCore::BpeHeapGuard wrong_cached{memory,Heap,regions,nullptr,nullptr,regions};
    assert(!wrong_cached.TryWrite(Base,gpu.data(),gpu.size(),kept) && writes==0);
    const std::array<VideoCore::BpeHeapGuard::Region,1> unknown{{{Base+0x20000,0x10000}}};
    VideoCore::BpeHeapGuard unknown_cached{memory,Heap,regions,nullptr,nullptr,unknown};
    assert(!unknown_cached.IsValid());
    const std::array<VideoCore::BpeHeapGuard::Region, 2> overlap{{{Base, 0x10000}, {Base + 0x8000, 0x10000}}};
    VideoCore::BpeHeapGuard bad_ranges{memory, Heap, overlap};
    assert(!bad_ranges.IsValid());
    std::cout << "BPE scoped readback guard: PASS\n";
}
