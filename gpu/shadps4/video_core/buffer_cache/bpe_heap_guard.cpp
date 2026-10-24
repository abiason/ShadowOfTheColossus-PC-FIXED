// SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <chrono>
#include <cstdio>
#include <cstdlib>

#include "core/memory.h"
#include "video_core/buffer_cache/bpe_heap_guard.h"

namespace VideoCore {

namespace {
// Block header: [0] previous physical block, [8] size | flags (bits 0-2). Free blocks carry tree links after
// the header: left, right, equal-size list (two links), parent | color
constexpr u64 HeaderSize = 0x10;
constexpr u64 FreeNodeSize = 0x38;
constexpr u64 SizeMask = ~u64{7};
// The heap hands out GPU-mapped direct memory above 4 GiB (seen up to ~0x4f6 GiB); anything outside user
// space is garbage. Reads through the backing reject unmapped addresses
constexpr VAddr HeapPointerLo = 0x100000000ULL;
constexpr VAddr HeapPointerHi = 0x10000000000ULL;
constexpr u64 MaxBlockSize = 0x100000000ULL;
constexpr size_t MaxTreeNodes = 1 << 16;
constexpr size_t MaxListNodes = 1 << 10;
constexpr size_t MaxChainSteps = 1 << 12;
struct GuardWriteProfile {
    using Clock = std::chrono::steady_clock;
    static bool Enabled() {
        static const bool enabled = [] { const char* v = std::getenv("SOTC_HEAP_GUARD_PROFILE");
                                         return v && std::strcmp(v, "1") == 0; }();
        return enabled;
    }
    bool enabled = Enabled(), writing = false;
    Clock::time_point start = enabled ? Clock::now() : Clock::time_point{}, write_start{};
    void BeginWrite() { if (enabled) { writing = true; write_start = Clock::now(); } }
    ~GuardWriteProfile() {
        if (!enabled) return;
        const auto now = Clock::now();
        struct Totals { Clock::time_point start{}; u64 calls{}, metadata_ns{}, write_ns{}; };
        static thread_local Totals totals;
        if (totals.start == Clock::time_point{}) totals.start = start;
        ++totals.calls;
        totals.metadata_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(
            (writing ? write_start : now) - start).count();
        if (writing) totals.write_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(now - write_start).count();
        if (now - totals.start >= std::chrono::seconds(5)) {
            std::fprintf(stderr, "SOTC GUARD WRITE PROFILE: calls=%llu metadata_ms=%.3f write_ms=%.3f\n",
                static_cast<unsigned long long>(totals.calls), totals.metadata_ns/1e6, totals.write_ns/1e6);
            totals = {.start = now};
        }
    }
};
} // namespace

BpeHeapGuard::BpeHeapGuard(Core::MemoryManager* memory_, VAddr heap_)
    : memory{memory_}, heap{heap_} {
    u64 heap_size = 0;
    if (!Read(heap + 0x30, &heap_size, sizeof(heap_size)) || heap_size < 0x1000000 ||
        heap_size > MaxBlockSize) {
        return;
    }
    valid = true;
    CollectFreeTree();
}

BpeHeapGuard::BpeHeapGuard(Core::MemoryManager* memory_, VAddr heap_,
                           std::span<const Region> regions_, Reader reader_, void* context_,
                           std::span<const Region> cached_)
    : regions{regions_.begin(), regions_.end()}, cached_regions{cached_.begin(), cached_.end()},
      scoped{true}, reader{reader_},
      reader_context{context_}, memory{memory_}, heap{heap_} {
    if (!memory || !heap || heap > HeapPointerHi - 0x1000 || regions.empty()) return;
    if (!std::is_sorted(regions.begin(),regions.end()))
        std::sort(regions.begin(), regions.end());
    VAddr end = 0;
    for (const auto& [base, size] : regions) {
        if (base < HeapPointerLo || base >= HeapPointerHi || !size ||
            size > HeapPointerHi - base || base < end) return;
        end = base + size;
    }
    std::sort(cached_regions.begin(), cached_regions.end());
    for (size_t i=0;i<cached_regions.size();++i) {
        if (!std::binary_search(regions.begin(),regions.end(),cached_regions[i]) ||
            (i && cached_regions[i]==cached_regions[i-1])) return;
    }
    valid = true;
}

bool BpeHeapGuard::Contains(VAddr addr, u64 size) const {
    if (!size || addr > HeapPointerHi || size > HeapPointerHi - addr) return false;
    const auto it = std::upper_bound(regions.begin(), regions.end(), addr,
        [](VAddr address, const Region& region) { return address < region.first; });
    if (it == regions.begin()) return false;
    const auto& region = *std::prev(it);
    return addr >= region.first && addr - region.first < region.second &&
           size <= region.second - (addr - region.first);
}

void BpeHeapGuard::Refresh() {
    runs.clear();
    free_blocks.clear();
    free_spans.clear();
    scoped_headers.clear(); headers_ready.clear();
    scoped_headers.resize(regions.size()); headers_ready.resize(regions.size());
    if (!scoped) CollectFreeTree();
}

bool BpeHeapGuard::TryWrite(VAddr addr, const u8* data, u64 size, u64& kept) {
    GuardWriteProfile profile;
    kept = 0;
    failure = "arguments-or-guard-invalid";
    if (!scoped || !valid || !data || !size || size > HeapPointerHi ||
        addr >= HeapPointerHi || size > HeapPointerHi - addr) return false;
    failure = "range-not-fully-mapped";
    if (memory->ClampRangeSize(addr, size) != size) return false;
    // Refresh under the caller's allocator lock. Do not retain backing runs.
    failure = "metadata-invalid";
    if (!locked_batch || !batch_ready) {
        Refresh();
        if (!valid) return false;
        batch_ready = locked_batch;
    }
    failure = "physical-chain-invalid";
    std::vector<Span> spans;
    for (const auto& [base, bytes] : regions) {
        const VAddr lo = std::max(base, addr), hi = std::min(base + bytes, addr + size);
        if (lo >= hi) continue;
        auto part = CollectSpans(lo, hi);
        spans.insert(spans.end(), part.begin(), part.end());
    }
    if (!valid) return false;
    std::sort(spans.begin(), spans.end());
    VAddr cursor = addr;
    failure = "metadata-unreadable";
    // All metadata reads must succeed before any guest byte is written.
    for (const auto& [lo_, hi_] : spans) {
        const VAddr lo = std::max({lo_, addr, cursor}), hi = std::min(hi_, addr + size);
        if (lo >= hi) continue;
        std::array<u8, FreeNodeSize> current{};
        if (hi - lo > current.size() || !Read(lo, current.data(), hi - lo)) return false;
        if (std::memcmp(current.data(), data + lo - addr, hi - lo)) kept += hi - lo;
        cursor = hi;
    }
    failure = "backing-write-failed";
    profile.BeginWrite();
    cursor = addr;
    for (const auto& [lo_, hi_] : spans) {
        const VAddr lo = std::max({lo_, addr, cursor}), hi = std::min(hi_, addr + size);
        if (lo >= hi) continue;
        if (lo > cursor && !memory->TryWriteBacking(std::bit_cast<void*>(cursor),
                                                   data + cursor - addr, lo - cursor)) return false;
        cursor = hi;
    }
    if (cursor < addr + size && !memory->TryWriteBacking(std::bit_cast<void*>(cursor),
                              data + cursor - addr, addr + size - cursor)) return false;
    if (!locked_batch) {
        runs.clear(); free_blocks.clear(); free_spans.clear();
        scoped_headers.clear(); headers_ready.clear();
    }
    failure = "none";
    return true;
}

bool BpeHeapGuard::Read(VAddr addr, void* out, u64 size) const {
    if (scoped) {
        if (!Contains(addr, size) && !(addr >= heap && addr - heap < 0x1000 &&
                                     size <= 0x1000 - (addr - heap))) return false;
        return reader ? reader(reader_context, addr, out, size) : memory->TryReadBacking(addr, out, size);
    }
    auto it = std::upper_bound(runs.begin(), runs.end(), addr,
                               [](VAddr value, const Run& run) { return value < run.start; });
    if (it == runs.begin() || addr - std::prev(it)->start >= std::prev(it)->size) {
        Run run{};
        run.ptr = memory->GetBackingRun(addr, &run.start, &run.size);
        if (!run.ptr) {
            // sotc: the heap object itself is a global of the eboot, outside the guest memory
            // the runtime maps (no backing view): its fields are read in place.
            if (addr >= heap && addr + size <= heap + 0x1000) {
                std::memcpy(out, std::bit_cast<const void*>(addr), size);
                return true;
            }
            return false;
        }
        it = std::next(runs.insert(it, run));
    }
    const Run& run = *std::prev(it);
    if (addr - run.start + size > run.size) {
        // Crosses into the next physical area: take the general path
        return memory->TryReadBacking(addr, out, size);
    }
    std::memcpy(out, run.ptr + (addr - run.start), size);
    return true;
}

bool BpeHeapGuard::IsHeapPointer(VAddr addr) const {
    return addr >= HeapPointerLo && addr < HeapPointerHi && (addr & 7) == 0 &&
           (!scoped || Contains(addr, 1));
}

void BpeHeapGuard::AddFreeBlock(VAddr block) {
    free_blocks.push_back(block);
}

void BpeHeapGuard::CollectFreeTree() {
    const VAddr sentinel = heap + 0x80;
    VAddr root = 0;
    Read(sentinel, &root, sizeof(root));
    VAddr pending = 0;
    if (Read(heap + 0xc0, &pending, sizeof(pending)) && IsHeapPointer(pending)) {
        AddFreeBlock(pending);
    }
    std::vector<VAddr> stack{root};
    size_t visited = 0;
    while (!stack.empty() && visited < MaxTreeNodes) {
        const VAddr node = stack.back();
        stack.pop_back();
        if (node == sentinel || !IsHeapPointer(node)) {
            continue;
        }
        std::array<u64, 7> words{};
        if (!Read(node - HeaderSize, words.data(), sizeof(words))) {
            continue;
        }
        ++visited;
        const u64 key = words[1] & SizeMask;
        if (key == 0 || key >= MaxBlockSize) {
            // Already corrupted: still keep what is left of it, but do not follow its links
            AddFreeBlock(node - HeaderSize);
            continue;
        }
        AddFreeBlock(node - HeaderSize);
        // Blocks of equal size hang off the tree node in a ring through the list links
        VAddr member = words[4];
        for (size_t i = 0; i < MaxListNodes && IsHeapPointer(member) && member != node; ++i) {
            AddFreeBlock(member - HeaderSize);
            VAddr next = 0;
            if (!Read(member + 0x10, &next, sizeof(next))) {
                break;
            }
            member = next;
        }
        stack.push_back(words[2]);
        stack.push_back(words[3]);
    }
    std::sort(free_blocks.begin(), free_blocks.end());
    free_blocks.erase(std::unique(free_blocks.begin(), free_blocks.end()), free_blocks.end());
    free_spans.reserve(free_blocks.size());
    for (const VAddr block : free_blocks) {
        free_spans.emplace_back(block, block + FreeNodeSize);
    }
}

bool BpeHeapGuard::NextBlock(VAddr block, VAddr& next) const {
    u64 size_flags = 0;
    if (!Read(block + 8, &size_flags, sizeof(size_flags))) {
        return false;
    }
    const u64 size = size_flags & SizeMask;
    if (size == 0 || size >= MaxBlockSize) {
        return false;
    }
    next = block + size + HeaderSize;
    // The next block must point back: this rejects anything that only looks like a header
    VAddr prev = 0;
    return IsHeapPointer(next) && Read(next, &prev, sizeof(prev)) && prev == block;
}

void BpeHeapGuard::CollectHeaders(VAddr lo, VAddr hi, std::vector<Span>& spans) const {
    // Start from the closest free block at or below the range, whose header is known to be real, and follow
    // the physical chain through the range
    auto it = std::upper_bound(free_blocks.begin(), free_blocks.end(), lo);
    std::vector<VAddr> starts;
    // Readbacks usually start at a binding base, i.e. the user pointer of an allocation: start from its
    // header too (accepted only if the next block points back to it)
    if (VAddr next = 0; lo > HeaderSize && NextBlock(lo - HeaderSize, next)) {
        starts.push_back(lo - HeaderSize);
    }
    if (it != free_blocks.begin()) {
        starts.push_back(*std::prev(it));
    }
    for (; it != free_blocks.end() && *it < hi; ++it) {
        starts.push_back(*it);
    }
    std::sort(starts.begin(), starts.end());
    VAddr covered_until = 0;
    for (VAddr block : starts) {
        if (block < covered_until) {
            continue;
        }
        for (size_t step = 0; step < MaxChainSteps && block < hi; ++step) {
            if (block + HeaderSize > lo) {
                spans.emplace_back(block, block + HeaderSize);
            }
            VAddr next = 0;
            if (!NextBlock(block, next)) {
                break;
            }
            block = next;
        }
        covered_until = block;
    }
}

std::vector<BpeHeapGuard::Span> BpeHeapGuard::CollectSpans(VAddr addr, VAddr end) {
    std::vector<Span> spans;
    for (auto it = std::lower_bound(free_spans.begin(), free_spans.end(),
                                    Span{addr > FreeNodeSize ? addr - FreeNodeSize : 0, 0});
         it != free_spans.end() && it->first < end; ++it) {
        if (it->second > addr) {
            spans.push_back(*it);
        }
    }
    if (scoped) {
        for (size_t region_index = 0; region_index < regions.size(); ++region_index) {
            const auto [base, bytes] = regions[region_index];
            if (base >= end || base + bytes <= addr) continue;
            if (locked_batch && headers_ready[region_index]) {
                for (const auto& span : scoped_headers[region_index])
                    if (span.first < end && span.second > addr) spans.push_back(span);
                continue;
            }
            std::vector<Span> headers;
            std::array<u64, 2> header{};
            if (std::binary_search(cached_regions.begin(),cached_regions.end(),Region{base,bytes})) {
                if (!Read(base,header.data(),HeaderSize) || (header[1]&SizeMask)!=bytes || (header[1]&7)!=3) {
                    valid=false; return {};
                }
                headers.emplace_back(base,base+HeaderSize);
                if (base<end && base+HeaderSize>addr) spans.push_back(headers.front());
                if (locked_batch) {
                    scoped_headers[region_index]=std::move(headers);
                    headers_ready[region_index]=true;
                }
                continue;
            }
            if (!Read(base, header.data(), HeaderSize) || header[1] != 3) {
                valid = false; return {};
            }
            headers.emplace_back(base, base + HeaderSize);
            VAddr previous = base, block = base + HeaderSize;
            bool terminal = false;
            for (size_t step = 0; step < MaxTreeNodes; ++step) {
                if (!Contains(block, HeaderSize) ||
                    !Read(block, header.data(), HeaderSize) || header[0] != previous) break;
                headers.emplace_back(block, block + HeaderSize);
                const u64 payload = header[1] & SizeMask;
                if (!payload) {
                    terminal = header[1] == 1 && block + HeaderSize == base + bytes;
                    break;
                }
                if (payload > bytes || block + HeaderSize > base + bytes ||
                    payload > base + bytes - block - HeaderSize) break;
                // EU 1.01 +0x48fac sets bit 0 on allocation; +0x49492 clears
                // it on free. A free block's first 40 payload bytes belong to
                // allocator links, independent of its position in the free tree.
                if (!(header[1] & 1))
                    headers.emplace_back(block + HeaderSize,
                        block + HeaderSize + std::min(payload, FreeNodeSize - HeaderSize));
                // +0x49476 reads the allocation's trailing debug id when bit 2
                // is set; these four bytes also belong to the CPU allocator.
                if (header[1] & 4)
                    headers.emplace_back(block + HeaderSize + payload - sizeof(u32),
                                         block + HeaderSize + payload);
                previous = block; block += HeaderSize + payload;
            }
            if (!terminal) { valid = false; return {}; }
            for (const auto& span : headers)
                if (span.first < end && span.second > addr) spans.push_back(span);
            if (locked_batch) {
                scoped_headers[region_index] = std::move(headers);
                headers_ready[region_index] = true;
            }
        }
    } else {
        CollectHeaders(addr, end, spans);
    }
    std::sort(spans.begin(), spans.end());
    return spans;
}

u64 BpeHeapGuard::Write(VAddr addr, const u8* data, u64 size) {
    const VAddr end = addr + size;
    const std::vector<Span> spans = CollectSpans(addr, end);

    u64 differing = 0;
    VAddr cursor = addr;
    const auto write = [&](VAddr lo, VAddr hi) {
        if (hi > lo) {
            memory->TryWriteBacking(std::bit_cast<void*>(lo), data + (lo - addr), hi - lo);
        }
    };
    for (const auto& [span_lo, span_hi] : spans) {
        const VAddr lo = std::max(span_lo, addr);
        const VAddr hi = std::min(span_hi, end);
        if (hi <= lo || hi <= cursor) {
            continue;
        }
        const VAddr keep_lo = std::max(lo, cursor);
        write(cursor, keep_lo);
        std::array<u8, FreeNodeSize> current{};
        const u64 len = hi - keep_lo;
        if (Read(keep_lo, current.data(), len) &&
            std::memcmp(current.data(), data + (keep_lo - addr), len) != 0) {
            differing += len;
        }
        cursor = hi;
    }
    write(cursor, end);
    return differing;
}

} // namespace VideoCore
