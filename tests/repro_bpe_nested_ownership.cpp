// SPDX-License-Identifier: GPL-2.0-or-later
// Regression for parent-first readback losing a nested allocator's headers.
#define main guard_fixture_original_main
#include "test_bpe_heap_guard.cpp"
#undef main

static void chain(VAddr base, u64 bytes) {
    put(base,0); put(base+8,3);
    put(base+16,base); put(base+24,bytes-48+1);
    put(base+bytes-16,base+16); put(base+bytes-8,1);
}
int main() {
    Core::MemoryManager memory;
    std::array<u8,0x10000> gpu; gpu.fill(0xa5);
    constexpr VAddr Child = Base + 0x1000;
    constexpr u64 ChildBytes = 0x2000;
    const std::array<VideoCore::BpeHeapGuard::Region,1> outer{{{Base,region.size()}}};
    const std::array<VideoCore::BpeHeapGuard::Region,1> inner{{{Child,ChildBytes}}};
    for (bool reverse : {false,true}) {
        reset(); chain(Child,ChildBytes);
        VideoCore::BpeHeapGuard parent{&memory,Heap,outer}, child{&memory,Heap,inner};
        parent.UseLockedBatch(); child.UseLockedBatch();
        const std::array<VideoCore::BpeHeapGuard*,2> owners = reverse
            ? std::array{&child,&parent} : std::array{&parent,&child};
        u64 kept=0;
        assert(VideoCore::BpeHeapGuard::TryWriteCombined(owners,Base,gpu.data(),gpu.size(),kept));
        assert(kept==96 && get(Child+8)==3 && get(Child+ChildBytes-8)==1);
        assert(get(Base+8)==3 && get(Base+region.size()-8)==1);
        assert(region[32]==0xa5 && region[0x1020]==0xa5);
        // Cached metadata remains valid for a second piece under the same locks.
        assert(VideoCore::BpeHeapGuard::TryWriteCombined(owners,Child+8,gpu.data(),32,kept));
        assert(get(Child+8)==3);
    }
    // Partially overlapping owners: the child's terminal lies beyond the parent.
    for (bool reverse : {false,true}) {
        reset(); chain(Base,0x5000); chain(Child,0x6000);
        const std::array<VideoCore::BpeHeapGuard::Region,1> a{{{Base,0x5000}}}, b{{{Child,0x6000}}};
        VideoCore::BpeHeapGuard parent{&memory,Heap,a}, child{&memory,Heap,b};
        const std::array<VideoCore::BpeHeapGuard*,2> owners = reverse
            ? std::array{&child,&parent} : std::array{&parent,&child};
        u64 kept=0;
        assert(VideoCore::BpeHeapGuard::TryWriteCombined(owners,Base,gpu.data(),0x8000,kept));
        assert(kept==96 && get(Base+0x4ff8)==1 && get(Base+0x6ff8)==1);
        assert(region[0x7000]==0xa5); // Unowned payload follows ordinary readback.
    }
    // Heap control objects, region descriptors and mutexes can also live in
    // parent payload. Even an empty child heap still owns its control metadata.
    reset(); chain(Child,ChildBytes);
    constexpr VAddr Control=Base+0x5000, Empty=Base+0x6000, Descriptor=Base+0x8000, Mutex=Base+0x9000;
    const std::array<VideoCore::BpeHeapGuard::Region,2> metadata{{{Descriptor,0x68},{Mutex,8}}};
    VideoCore::BpeHeapGuard control_parent{&memory,Heap,outer,nullptr,nullptr,{},metadata};
    VideoCore::BpeHeapGuard control_child{&memory,Control,inner};
    VideoCore::BpeHeapGuard empty_child{&memory,Empty,{}};
    const std::array control_owners{&control_parent,&control_child,&empty_child};
    u64 control_kept=0;
    assert(VideoCore::BpeHeapGuard::TryWriteCombined(control_owners,Base,gpu.data(),gpu.size(),control_kept));
    for (const auto& [base,bytes] : std::array<VideoCore::BpeHeapGuard::Region,4>{{
             {Control,0xf0},{Empty,0xf0},{Descriptor,0x68},{Mutex,8}}})
        for (u64 i=0;i<bytes;++i) assert(region[base-Base+i]==0);
    assert(region[0x5100]==0xa5 && region[0x8100]==0xa5 && get(Child+8)==3);
    // An invalid later owner must not leave the earlier owner partially written.
    reset(); chain(Child,ChildBytes); put(Child+ChildBytes-16,0);
    const auto before=region;
    VideoCore::BpeHeapGuard parent{&memory,Heap,outer}, child{&memory,Heap,inner};
    const std::array owners{&parent,&child};
    u64 kept=0;
    assert(!VideoCore::BpeHeapGuard::TryWriteCombined(owners,Base,gpu.data(),gpu.size(),kept));
    assert(writes==0 && region==before);
    // Repeated/aliased owners must count and protect each byte only once.
    reset();
    VideoCore::BpeHeapGuard duplicate{&memory,Heap,outer};
    const std::array duplicates{&duplicate,&duplicate};
    assert(VideoCore::BpeHeapGuard::TryWriteCombined(duplicates,Base,gpu.data(),gpu.size(),kept));
    assert(kept==48);
    std::cout << "BPE combined ownership guard: PASS\n";
    return 0;
}
