/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Include the implementation so the actual host/backing adapter is exercised too. */
#include "../src/runtime_heap_watch.c"
#include <assert.h>
#include <sys/mman.h>

enum { TABLE=0x20000, OBJECT=0x30000, BITMAP=0x40000, ARENA=0x50000, SECOND=0x60000 };
static uint64_t table[SOTC_HEAP_SLOTS], bitmap[1024];
static unsigned char object[0xf0], pools[SOTC_PAGE_POOLS][0xa0];
static unsigned char external[0x20000], second[0xf0];
static int batch_table_reads, batch_change_table, batch_change_identity;
static const uint64_t External=UINT64_C(0x100000000);
static int read_calls, fail_second_chunk, mutate_list, mutate_cached, cached_reads;
static const uintptr_t ClassImage=0x100000, ClassTable=0x1695b70;
static uint64_t class_functions[2];
static void field(size_t at,uint64_t value) { memcpy(object+at,&value,8); }
static int fixture_read(void *context,uintptr_t address,void *out,size_t size) {
    (void)context;
    ++read_calls;
    const void *source=NULL;
    if (address>=TABLE && address-TABLE<sizeof(table) && size<=sizeof(table)-(address-TABLE))
        source=(unsigned char *)table+address-TABLE;
    if (address>=OBJECT && address-OBJECT<sizeof(object) && size<=sizeof(object)-(address-OBJECT))
        source=object+address-OBJECT;
    if (address>=BITMAP && address-BITMAP<sizeof(bitmap) && size<=sizeof(bitmap)-(address-BITMAP)) {
        if (fail_second_chunk && address>=BITMAP+512*8) return 0;
        source=(unsigned char *)bitmap+address-BITMAP;
    }
    if (address>=ARENA && address-ARENA<sizeof(pools) && size<=sizeof(pools)-(address-ARENA))
        source=(unsigned char *)pools+address-ARENA;
    if (address==ClassTable+0xa0 && size==sizeof(class_functions)) source=class_functions;
    if (address>=External && address-External<sizeof(external) && size<=sizeof(external)-(address-External))
        source=external+address-External;
    if (!source) return 0;
    memcpy(out,source,size);
    if (mutate_list && address==OBJECT+0x38 && size==0x28) ((unsigned char *)out)[0]^=1;
    if (mutate_cached && address==OBJECT+0xc8 && size==8 && ++cached_reads==2)
        ((unsigned char *)out)[2]^=1;
    return 1;
}
static RuntimeHeapSample snapshot(void) {
    RuntimeHeapSample samples[SOTC_HEAP_SLOTS];
    const size_t n=runtime_heap_inventory(TABLE,fixture_read,NULL,samples,SOTC_HEAP_SLOTS);
    assert(n==1);
    return samples[0];
}
static void reset(void) {
    memset(table,0,sizeof(table)); memset(bitmap,0,sizeof(bitmap)); memset(object,0,sizeof(object));
    table[3]=OBJECT;
    field(0,0x12345000); field(0x28,0x1000000000); field(0x30,1024*1024);
    field(0x50,BITMAP); field(0x58,2); field(0x60,100);
    read_calls=0; fail_second_chunk=0;
}

static int pins, callbacks, change_class_on_pin, lifetime_maps, lifetime_external;
void runtime_memory_read_pin(void) {
    ++pins;
    if (change_class_on_pin) field(0,ClassTable+8);
}
void runtime_memory_read_unpin(void) { assert(pins>0); --pins; }
static int retry_yields, release_on_yield, remove_on_yield, corrupt_on_yield;
/* Deterministic scheduler interposition: inspect cleanup before another thread
 * is modeled as releasing its lock, removing a heap or changing its regions. */
int sched_yield(void) {
    assert(pins==0 && word64(object+0x78)==0);
    ++retry_yields;
    if (release_on_yield && retry_yields==release_on_yield) {
        uint64_t value=0;
        memcpy(second+0x78,&value,8);
        if (remove_on_yield) table[7]=0;
        if (corrupt_on_yield) {
            value=UINT64_MAX; memcpy(second+0xb8,&value,8);
        }
    }
    return 0;
}
static void guarded_visit(void *context,uintptr_t address,const RuntimeGuardRegion *regions,
                           size_t count,RuntimeGuardRead read,void *reader) {
    (void)context; (void)regions;
    assert(pins==1 && address==OBJECT && count==0);
    uint64_t held=0;
    assert(read(reader,UINT64_C(0x100000000),&held,8) && held==UINT64_MAX);
    ++callbacks;
}

typedef struct { uint64_t expected_base,mutex; unsigned calls; } LifetimeContext;
static void lifetime_visit(void *opaque,uintptr_t address,const RuntimeGuardRegion *regions,
                            size_t count,RuntimeGuardRead read,void *reader) {
    LifetimeContext *state=opaque;
    assert(pins==1 && address==OBJECT && count==1);
    assert(regions[0].base==state->expected_base && regions[0].bytes==0x10000);
    assert(regions[0].flags==RUNTIME_GUARD_REGION_CACHED);
    uint64_t held=0;
    assert(read(reader,state->mutex,&held,8) && held==UINT64_MAX);
    ++state->calls;
}

static void lifetime_batch_visit(void *opaque,const RuntimeGuardOwner *owners,size_t count,
                                 RuntimeGuardRead read,void *reader) {
    assert(count==1 && owners[0].metadata_count==3);
    assert(owners[0].metadata[0].base==OBJECT && owners[0].metadata[0].bytes==0xf0);
    assert(owners[0].metadata[2].base==ARENA && owners[0].metadata[2].bytes==0x68);
    lifetime_visit(opaque,owners[0].heap,owners[0].regions,owners[0].count,read,reader);
}

/* Synthetic guest mappings deliberately have separate physical backing arrays. */
static const uintptr_t Guest=UINT64_C(0x100000000);
static unsigned char backings[2][16];
static int hole, inaccessible;
static int fixture_host_read(uintptr_t address,void *out,size_t size) {
    if (address>=ClassImage+0x2dfaab0 && address-ClassImage-0x2dfaab0<sizeof(table) &&
        size<=sizeof(table)-(address-ClassImage-0x2dfaab0)) {
        memcpy(out,(unsigned char *)table+address-ClassImage-0x2dfaab0,size);
        if (batch_change_table && ++batch_table_reads==2) ((uint64_t *)out)[7]=0;
        return 1;
    }
    if (address==ClassTable+0xa0 && size==sizeof(class_functions)) {
        memcpy(out,class_functions,size); return 1;
    }
    if (address>=(uintptr_t)object && address-(uintptr_t)object<sizeof(object) &&
        size<=sizeof(object)-(address-(uintptr_t)object)) {
        memcpy(out,(void *)address,size); return 1;
    }
    const uintptr_t base=(uintptr_t)backings;
    if (address<base || address-base>=sizeof(backings) ||
        size>sizeof(backings)-(address-base)) return 0;
    memcpy(out,(const void *)address,size);
    return 1;
}
int runtime_memory_region(uintptr_t address,uintptr_t *start,uintptr_t *end,int *mapped) {
    if (address>=SECOND && address-SECOND<sizeof(second)) {
        *start=SECOND; *end=SECOND+sizeof(second); *mapped=1; return 1;
    }
    if (lifetime_maps && address>=ARENA && address-ARENA<sizeof(pools)) {
        *start=ARENA; *end=ARENA+sizeof(pools); *mapped=1; return 1;
    }
    if (lifetime_maps && lifetime_external && address>=External && address-External<sizeof(external)) {
        *start=External; *end=External+sizeof(external); *mapped=1; return 1;
    }
    if (address>=OBJECT && address-OBJECT<sizeof(object)) {
        *start=OBJECT; *end=OBJECT+sizeof(object); *mapped=1; return 1;
    }
    if (address<Guest || address-Guest>=32) return 0;
    const size_t region=(address-Guest)/16;
    *start=Guest+region*16; *end=*start+16;
    *mapped=!(hole && region==1);
    return 1;
}
const unsigned char *runtime_memory_backing_pointer(uintptr_t address) {
    if (address>=SECOND && address-SECOND<sizeof(second)) {
        if (batch_change_identity && address==SECOND+0x78) field(0,ClassTable+8);
        return second+address-SECOND;
    }
    if (lifetime_maps && address>=ARENA && address-ARENA<sizeof(pools)) return (unsigned char *)pools+address-ARENA;
    if (lifetime_maps && lifetime_external && address>=External && address-External<sizeof(external))
        return external+address-External;
    if (address>=OBJECT && address-OBJECT<sizeof(object)) return object+address-OBJECT;
    if (inaccessible) return (const unsigned char *)1;
    if (address<Guest || address-Guest>=32) return NULL;
    /* Reverse the physical order to rule out a single memcpy across guest VMAs. */
    const size_t region=(address-Guest)/16;
    return backings[1-region]+(address-Guest)%16;
}

static void batch_visit(void *opaque,const RuntimeGuardOwner *owners,size_t count,
                         RuntimeGuardRead read,void *reader) {
    (void)opaque;
    assert(pins==1 && count==2 && owners[0].heap==OBJECT && owners[1].heap==SECOND);
    assert(owners[0].count==0 && owners[1].count==0);
    assert(owners[0].metadata_count==2 && owners[1].metadata_count==2);
    assert(owners[0].metadata[0].base==OBJECT && owners[0].metadata[0].bytes==0xf0);
    assert(owners[0].metadata[1].base==OBJECT+0x78 && owners[0].metadata[1].bytes==8);
    uint64_t a=0,b=0;
    assert(read(reader,OBJECT+0x78,&a,8) && a==UINT64_MAX);
    assert(read(reader,SECOND+0x70,&b,8));
    assert(read(reader,b,&a,8) && a==UINT64_MAX);
    ++callbacks;
}

static void init_batch_fixture(void) {
    class_functions[0]=ClassImage+0x48c80; class_functions[1]=ClassImage+0x493d0;
    field(0,ClassTable); field(0x70,OBJECT+0x78); field(0x78,0);
    field(0x40,OBJECT+0x38); field(0x48,OBJECT+0x38); field(0x58,0); field(0xb8,0);
    memcpy(second,object,sizeof(second));
    uint64_t value=SECOND+0x78; memcpy(second+0x70,&value,8);
    value=SECOND+0x38; memcpy(second+0x40,&value,8); memcpy(second+0x48,&value,8);
    table[7]=SECOND;
    guard_watch=(HeapWatch){.image=ClassImage,.size=0x3000000,.read_host=fixture_host_read};
    guard_enabled=1;
}
static void retry_removed_visit(void *opaque,const RuntimeGuardOwner *owners,size_t count,
                                RuntimeGuardRead read,void *reader) {
    (void)opaque;
    assert(pins==1 && count==1 && owners[0].heap==OBJECT);
    uint64_t value=0;
    assert(read(reader,OBJECT+0x78,&value,8) && value==UINT64_MAX);
    ++callbacks;
}

static unsigned char *image_fixture;
static const size_t ImageFixtureSize=0x3000000;
static int image_fixture_read(uintptr_t address,void *out,size_t size) {
    if (address<(uintptr_t)image_fixture || address-(uintptr_t)image_fixture>=ImageFixtureSize ||
        size>ImageFixtureSize-(address-(uintptr_t)image_fixture)) return 0;
    memcpy(out,(void *)address,size); return 1;
}
static void image_batch_visit(void *opaque,const RuntimeGuardOwner *owners,size_t count,
                              RuntimeGuardRead read,void *reader) {
    (void)opaque;
    assert(pins==1 && count==1 && owners[0].count==0);
    const uintptr_t address=(uintptr_t)image_fixture+0x2dfc700;
    assert(owners[0].heap==address && owners[0].metadata[1].base==address+0x60);
    uint64_t value=0;
    assert(read(reader,address+0x60,&value,8) && value==UINT64_MAX);
    ++callbacks;
}

int main(int argc,char **argv) {
    assert(argc==2);
    reset();
    if (!strcmp(argv[1],"valid")) {
        bitmap[0]=UINT64_C(0x3ff);
        bitmap[1]=UINT64_C(0x3ff);
        const RuntimeHeapSample s=snapshot();
        assert(s.id==3 && s.address==OBJECT && s.readable && s.pool_valid);
        assert(s.class_address==0x12345000 && s.base==0x1000000000 && s.bytes==1024*1024);
        assert(s.pages==100 && s.free_pages==20);
        assert(!strcmp(s.pool_status,"valid"));
        assert(s.candidate_bitmap==BITMAP && s.candidate_words==2 && s.candidate_pages==100);
        assert(table[3]==OBJECT && bitmap[0]==0x3ff); /* No guest writes. */
    } else if (!strcmp(argv[1],"padding")) {
        bitmap[1]=~UINT64_C(0)<<36;
        RuntimeHeapSample s=snapshot();
        assert(s.pool_valid && s.free_pages==0);
        /* +0x5c is not part of the u32 bitmap word count. */
        field(0x58,UINT64_C(0xaaaaaaaa00000002));
        s=snapshot();
        assert(s.pool_valid && s.free_pages==0);
    } else if (!strcmp(argv[1],"invalid")) {
        const uint64_t bad_words[]={0,0x10001};
        for (size_t i=0;i<2;++i) {
            field(0x58,bad_words[i]);
            const RuntimeHeapSample s=snapshot();
            assert(!s.pool_valid && !strcmp(s.pool_status,"word-count-invalid"));
            assert(s.candidate_words==bad_words[i] && read_calls==2*(int)(i+1));
        }
        field(0x58,2);
        const uint64_t bad_pages[]={0,129};
        for (size_t i=0;i<2;++i) {
            field(0x60,bad_pages[i]);
            const RuntimeHeapSample s=snapshot();
            assert(!s.pool_valid && !strcmp(s.pool_status,"page-count-invalid"));
            assert(s.candidate_pages==bad_pages[i]);
        }
        field(0x60,100);
        const uint64_t bad_bitmaps[]={0,1,UINT64_MAX-7,0x60000};
        for (size_t i=0;i<4;++i) {
            field(0x50,bad_bitmaps[i]);
            const RuntimeHeapSample s=snapshot();
            assert(s.readable && !s.pool_valid && s.pages==0 && s.free_pages==0);
            assert(!strcmp(s.pool_status,i==3 ? "bitmap-unreadable" : "bitmap-address-invalid"));
            assert(s.candidate_bitmap==bad_bitmaps[i]);
        }
        table[3]=OBJECT+0x1000;
        const RuntimeHeapSample s=snapshot();
        assert(!s.readable && !strcmp(s.pool_status,"object-unreadable"));
    } else if (!strcmp(argv[1],"chunks")) {
        field(0x58,513); field(0x60,512*64+5);
        for (size_t i=0;i<513;++i) bitmap[i]=UINT64_MAX;
        RuntimeHeapSample s=snapshot();
        assert(s.pool_valid && s.pages==512*64+5 && s.free_pages==s.pages);
        fail_second_chunk=1;
        s=snapshot();
        assert(s.readable && !s.pool_valid && !s.free_pages); /* Not a partial count. */
        assert(!strcmp(s.pool_status,"bitmap-unreadable"));
        assert(s.candidate_pages==512*64+5);
    } else if (!strcmp(argv[1],"bounds")) {
        RuntimeHeapSample output[2]={{0},{.id=999}};
        table[4]=OBJECT;
        assert(runtime_heap_inventory(TABLE,fixture_read,NULL,output,1)==1);
        assert(output[1].id==999);
        assert(runtime_heap_inventory(UINTPTR_MAX-8,fixture_read,NULL,output,1)==0);
        assert(runtime_heap_inventory(TABLE,NULL,NULL,output,1)==0);
        assert(runtime_heap_inventory(TABLE,fixture_read,NULL,NULL,1)==0);
        assert(runtime_heap_inventory(TABLE,fixture_read,NULL,output,0)==0);
        assert(runtime_heap_inventory(0x60000,fixture_read,NULL,output,1)==0);
        memset(table,0,sizeof(table)); table[0]=8; table[1]=UINT64_MAX;
        read_calls=0;
        assert(runtime_heap_inventory(TABLE,fixture_read,NULL,output,2)==2);
        assert(!output[0].readable && !output[1].readable && read_calls==1);
        assert(!strcmp(output[0].pool_status,"object-address-invalid"));
        assert(!strcmp(output[1].pool_status,"object-address-invalid"));
    } else if (!strcmp(argv[1],"backing")) {
        HeapWatch state={.read_host=fixture_host_read};
        unsigned char out[32];
        memset(backings[0],0xab,16); memset(backings[1],0xcd,16);
        assert(watch_read(&state,Guest,out,32));
        for (size_t i=0;i<32;++i) assert(out[i]==(i<16 ? 0xcd : 0xab));
        runtime_memory_read_pin();
        assert(guard_pinned_read(&state,Guest,out,32));
        for (size_t i=0;i<32;++i) assert(out[i]==(i<16 ? 0xcd : 0xab));
        hole=1;
        assert(!guard_pinned_read(&state,Guest,out,32));
        assert(!guard_pinned_read(&state,UINTPTR_MAX-1,out,32));
        runtime_memory_read_unpin();
        assert(!watch_read(&state,Guest,out,32));
        hole=0; inaccessible=1;
        assert(!watch_read(&state,Guest,out,32));
        assert(!watch_read(&state,UINTPTR_MAX-1,out,32));
        state=(HeapWatch){.image=(uintptr_t)backings,.size=sizeof(backings),
                          .read_host=fixture_host_read};
        assert(watch_read(&state,(uintptr_t)backings,out,32));
        unsetenv("SOTC_HEAP_WATCH");
        assert(!runtime_heap_watch_start(0x10000,0x3000000));
        setenv("SOTC_HEAP_WATCH","1",1);
        assert(!runtime_heap_watch_start(0x10000,0x3000000)); /* Kernel read rejects bad image. */
    } else if (!strcmp(argv[1],"pools")) {
        RuntimeHeapSample out[4];
        table[0]=ARENA;
        memset(pools,0,sizeof(pools));
        /* Three independent descriptors; the next structure is not a pool. */
        for (size_t i=0;i<3;++i) {
            uint64_t pointer=BITMAP+i*8, pages=64;
            uint32_t words=1;
            memcpy(pools[i]+0x50,&pointer,8);
            memcpy(pools[i]+0x58,&words,4);
            memcpy(pools[i]+0x60,&pages,8);
        }
        bitmap[0]=0xff; bitmap[1]=0; bitmap[2]=UINT64_MAX;
        out[3].id=999;
        assert(runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,4)==3);
        assert(out[3].id==999);
        for (size_t i=0;i<3;++i) {
            assert(out[i].id==i && out[i].address==ARENA+i*0xa0);
            assert(out[i].readable && out[i].pool_valid && out[i].pages==64);
        }
        assert(out[0].free_pages==8 && out[1].free_pages==0 && out[2].free_pages==64);
        memset(pools[2],0,sizeof(pools[2]));
        assert(runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,4)==3);
        assert(out[2].readable && !out[2].pool_valid);
        assert(!strcmp(out[2].pool_status,"word-count-invalid"));
        assert(runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,1)==1);
        assert(!runtime_page_pool_inventory(TABLE,NULL,NULL,out,4));
        assert(!runtime_page_pool_inventory(TABLE,fixture_read,NULL,NULL,4));
        assert(!runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,0));
        table[0]=UINT64_MAX;
        assert(!runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,4));
        table[0]=0;
        assert(!runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,4));
        table[0]=ARENA+8;
        assert(runtime_page_pool_inventory(TABLE,fixture_read,NULL,out,4)==3);
        assert(!out[0].pool_valid); /* Do not silently treat root as the first bitmap. */
    } else if (!strcmp(argv[1],"regions")) {
        RuntimeHeapRegion regions[2]; size_t count; const char *status;
        const uint64_t sentinel=OBJECT+0x38;
        field(0x40,ARENA+0xa0); field(0x48,ARENA); field(0x58,2);
        for (size_t i=0;i<2;++i) {
            uint64_t values[13]={0};
            values[0]=ARENA+i*0xa0; values[1]=i ? ARENA : sentinel;
            values[2]=i ? sentinel : ARENA+0xa0; values[3]=sentinel;
            values[11]=0x20000; values[12]=UINT64_C(0x100000000)+i*0x40000;
            memcpy(pools[i],values,sizeof(values));
        }
        assert(runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(count==2 && !strcmp(status,"valid"));
        assert(regions[0].base==UINT64_C(0x100000000) && regions[1].bytes==0x20000);
        mutate_list=1;
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(count==0 && !strcmp(status,"list-changed")); mutate_list=0;
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,1,&count,&status));
        assert(!count && !strcmp(status,"capacity-exceeded"));
        pools[1][8]^=8;
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"links-inconsistent")); pools[1][8]^=8;
        uint64_t overlap=UINT64_C(0x100000000);
        memcpy(pools[1]+0x60,&overlap,8);
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"ranges-overlap"));
        overlap=UINT64_MAX; memcpy(pools[1]+0x60,&overlap,8);
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"range-invalid"));
        field(0x58,3);
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        field(0x58,0); field(0x40,sentinel); field(0x48,sentinel);
        assert(runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"valid"));
        assert(!runtime_bpe_heap_regions(OBJECT,NULL,NULL,regions,2,&count,&status));
        assert(!runtime_bpe_heap_regions(OBJECT,fixture_read,NULL,regions,2,NULL,&status));
    } else if (!strcmp(argv[1],"external")) {
        RuntimeHeapRegion regions[2]; size_t count; const char *status;
        field(0x40,OBJECT+0x38); field(0x48,OBJECT+0x38); field(0x58,0);
        field(0xb8,External);
        uint64_t dummy[2]={External+0x10000,3};
        uint64_t block[2]={External,0x10000-48+1};
        uint64_t end[2]={External+16,1};
        memcpy(external,dummy,16); memcpy(external+16,block,16);
        memcpy(external+0x10000-16,end,16);
        dummy[0]=0; block[0]=External+0x10000; end[0]=External+0x10000+16;
        memcpy(external+0x10000,dummy,16); memcpy(external+0x10000+16,block,16);
        memcpy(external+0x20000-16,end,16);
        assert(runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(count==2 && regions[0].base==External && regions[1].bytes==0x10000);
        assert(!regions[0].descriptor && !regions[1].descriptor);
        uint64_t mixed[13]={0};
        mixed[0]=ARENA; mixed[1]=OBJECT+0x38; mixed[2]=OBJECT+0x38; mixed[3]=OBJECT+0x38;
        mixed[11]=0x10000; mixed[12]=External;
        memcpy(pools[0],mixed,sizeof(mixed));
        field(0x40,ARENA); field(0x48,ARENA); field(0x58,1);
        assert(runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(count==2 && regions[0].descriptor==ARENA && !regions[1].descriptor);
        field(0x40,OBJECT+0x38); field(0x48,OBJECT+0x38); field(0x58,0);
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,1,&count,&status));
        assert(!count && !strcmp(status,"capacity-exceeded"));
        external[0x10000]=1;
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count); external[0x10000]=0;
        memcpy(external+0x10000,&External,8);
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count); memset(external+0x10000,0,8);
        external[16]^=8;
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"block-chain-invalid")); external[16]^=8;
        external[0x10000-8]=3;
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"block-chain-invalid"));
        field(0xb8,0);
        assert(runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count);
        /* A managed descriptor must also occur in the physical region list. */
        uint64_t node[13]={0};
        node[0]=ARENA; node[1]=OBJECT+0x38; node[2]=OBJECT+0x38; node[3]=OBJECT+0x38;
        node[11]=0x10000; node[12]=External;
        memcpy(pools[0],node,sizeof(node));
        field(0x40,ARENA); field(0x48,ARENA); field(0x58,1);
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"managed-region-missing"));
        memset(external,0,8); field(0xb8,External);
        assert(runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(count==1 && regions[0].descriptor==ARENA);
    } else if (!strcmp(argv[1],"cached")) {
        RuntimeHeapRegion regions[2]; size_t count; const char *status;
        const uint64_t sentinel=OBJECT+0x38;
        field(0x40,ARENA+0xa0); field(0x48,ARENA); field(0x58,2);
        field(0xb8,External); field(0xc8,External+0x10000);
        for (size_t i=0;i<2;++i) {
            uint64_t node[13]={0};
            node[0]=ARENA+i*0xa0; node[1]=i ? ARENA : sentinel;
            node[2]=i ? sentinel : ARENA+0xa0; node[3]=sentinel;
            node[11]=0x10000; node[12]=External+i*0x10000;
            memcpy(pools[i],node,sizeof(node));
        }
        uint64_t header[2]={0,3}; memcpy(external,header,16);
        header[1]=0x10003; memcpy(external+0x10000,header,16);
        assert(runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(count==2 && !regions[0].flags && regions[1].flags==RUNTIME_HEAP_REGION_CACHED);
        mutate_cached=1; cached_reads=0;
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"region-head-changed")); mutate_cached=0;
        header[1]=0x20003; memcpy(external+0x10000,header,16);
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"cached-region-header-invalid"));
        field(0xc8,External);
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"cached-region-also-active"));
        field(0xc8,External+0x20000);
        assert(!runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,2,&count,&status));
        assert(!count && !strcmp(status,"cached-region-unmanaged"));
        uint64_t only[13]={0};
        only[0]=ARENA; only[1]=sentinel; only[2]=sentinel; only[3]=sentinel;
        only[11]=0x10000; only[12]=External+0x10000;
        memcpy(pools[0],only,sizeof(only));
        field(0x40,ARENA); field(0x48,ARENA); field(0x58,1);
        field(0xb8,0); field(0xc8,External+0x10000);
        header[1]=0x10003; memcpy(external+0x10000,header,16);
        assert(runtime_bpe_all_regions(OBJECT,fixture_read,NULL,regions,1,&count,&status));
        assert(count==1 && regions[0].flags==RUNTIME_HEAP_REGION_CACHED);
    } else if (!strcmp(argv[1],"guard")) {
        unsetenv("SOTC_HEAP_GUARD_LINUX");
        runtime_heap_guard_start(ClassImage,0x3000000);
        assert(!guard_enabled);
        setenv("SOTC_HEAP_GUARD_LINUX","0",1);
        runtime_heap_guard_start(ClassImage,0x3000000);
        assert(!guard_enabled);
        unsetenv("SOTC_HEAP_GUARD_LINUX");
        class_functions[0]=ClassImage+0x48c80; class_functions[1]=ClassImage+0x493d0;
        field(0,ClassTable); field(0x70,Guest);
        field(0x40,OBJECT+0x38); field(0x48,OBJECT+0x38); field(0x58,0); field(0xb8,0);
        guard_watch=(HeapWatch){.image=ClassImage,.size=0x3000000,.read_host=fixture_host_read};
        guard_enabled=1; guard_profile=1; guard_timing=(GuardProfile){0};
        runtime_heap_guard_visit(guarded_visit,NULL);
        assert(callbacks==1 && pins==0);
        uint64_t mutex=123; memcpy(backings[1],&mutex,8);
        runtime_heap_guard_visit(guarded_visit,NULL);
        assert(callbacks==1 && pins==0); /* Busy allocator is skipped, never waited on. */
        memcpy(&mutex,backings[1],8); assert(mutex==123);
        memset(backings[1],0,8);
        field(0xb8,UINT64_MAX);
        runtime_heap_guard_visit(guarded_visit,NULL);
        memcpy(&mutex,backings[1],8);
        assert(callbacks==1 && pins==0 && mutex==0); /* Release after invalid snapshot. */
        field(0xb8,0); guard_enabled=0;
        runtime_heap_guard_visit(guarded_visit,NULL);
        assert(callbacks==1 && pins==0);
        guard_enabled=1; field(0x70,0);
        runtime_heap_guard_visit(guarded_visit,NULL);
        assert(callbacks==1 && pins==0);
        assert(guard_timing.visits==4);
        guard_timing.start=guard_clock()-UINT64_C(5000000000);
        runtime_heap_guard_visit(guarded_visit,NULL);
        assert(guard_timing.visits==0 && callbacks==1 && pins==0);
    } else if (!strcmp(argv[1],"image-mutex")) {
        image_fixture=mmap(NULL,ImageFixtureSize,PROT_READ|PROT_WRITE,
                            MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);
        assert(image_fixture!=MAP_FAILED);
        const uintptr_t image=(uintptr_t)image_fixture, address=image+0x2dfc700;
        uint64_t *heap=(uint64_t *)address;
        heap[0]=(uint64_t)image+0x1595b70;
        heap[0x40/8]=address+0x38; heap[0x48/8]=address+0x38;
        heap[0x70/8]=address+0x60;
        uint64_t *functions=(uint64_t *)(image+0x1595b70+0xa0);
        functions[0]=image+0x48c80; functions[1]=image+0x493d0;
        ((uint64_t *)(image+0x2dfaab0))[3]=address;
        guard_watch=(HeapWatch){.image=image,.size=ImageFixtureSize,.read_host=image_fixture_read};
        guard_enabled=1;
        assert(runtime_heap_guard_batch(image_batch_visit,NULL));
        assert(callbacks==1 && pins==0 && heap[0x60/8]==0);
        heap[0x60/8]=123;
        assert(!runtime_heap_guard_batch(image_batch_visit,NULL));
        assert(callbacks==1 && pins==0 && heap[0x60/8]==123);
        heap[0x60/8]=0; heap[0x70/8]=address+0x68;
        assert(!runtime_heap_guard_batch(image_batch_visit,NULL));
        assert(callbacks==1 && pins==0 && heap[0x68/8]==0);
        assert(!munmap(image_fixture,ImageFixtureSize));
    } else if (!strcmp(argv[1],"retry")) {
        init_batch_fixture();
        uint64_t busy=123;
        memcpy(second+0x78,&busy,8); release_on_yield=1;
        assert(runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==1 && retry_yields==1 && pins==0);
        assert(word64(object+0x78)==0 && word64(second+0x78)==0);
        assert(guard_batch_timing.visits==1 && guard_batch_timing.tries==2 &&
               guard_batch_timing.recovered==1 && guard_batch_timing.bypassed==0);
        memcpy(second+0x78,&busy,8); retry_yields=0; release_on_yield=2;
        assert(runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==2 && retry_yields==2 && pins==0);
        assert(guard_batch_timing.visits==2 && guard_batch_timing.tries==5 &&
               guard_batch_timing.recovered==2 && guard_batch_timing.bypassed==0);
        memcpy(second+0x78,&busy,8); retry_yields=0; release_on_yield=0;
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==2 && retry_yields==2 && pins==0);
        assert(word64(object+0x78)==0 && word64(second+0x78)==123);
        assert(guard_batch_timing.visits==3 && guard_batch_timing.tries==8 &&
               guard_batch_timing.busy_exhausted==1 && guard_batch_timing.invalid==0);
    } else if (!strcmp(argv[1],"retry-removed")) {
        init_batch_fixture();
        uint64_t busy=123; memcpy(second+0x78,&busy,8);
        release_on_yield=1; remove_on_yield=1;
        assert(runtime_heap_guard_batch(retry_removed_visit,NULL));
        assert(callbacks==1 && retry_yields==1 && pins==0 && table[7]==0);
        assert(word64(object+0x78)==0 && word64(second+0x78)==0);
    } else if (!strcmp(argv[1],"retry-invalid")) {
        init_batch_fixture();
        uint64_t busy=123; memcpy(second+0x78,&busy,8);
        release_on_yield=1; corrupt_on_yield=1;
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==0 && retry_yields==1 && pins==0);
        assert(word64(object+0x78)==0 && word64(second+0x78)==0);
        assert(guard_batch_timing.visits==1 && guard_batch_timing.tries==2 &&
               guard_batch_timing.invalid==1 && guard_batch_timing.busy_exhausted==0);
    } else if (!strcmp(argv[1],"batch")) {
        init_batch_fixture();
        uint64_t value=0;
        assert(runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==1 && pins==0 && word64(object+0x78)==0 && word64(second+0x78)==0);
        value=123; memcpy(second+0x78,&value,8);
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==1 && pins==0 && word64(object+0x78)==0 && word64(second+0x78)==123);
        value=0; memcpy(second+0x78,&value,8);
        batch_change_identity=1;
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==1 && pins==0 && word64(object+0x78)==0 && word64(second+0x78)==0);
        batch_change_identity=0; field(0,ClassTable);
        batch_change_table=1; batch_table_reads=0;
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==1 && pins==0 && word64(object+0x78)==0 && word64(second+0x78)==0);
        batch_change_table=0;
        value=UINT64_MAX; memcpy(second+0xb8,&value,8);
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==1 && pins==0 && word64(object+0x78)==0 && word64(second+0x78)==0);
        value=0; memcpy(second+0xb8,&value,8);
        // Shared mutex is acquired once, not mistaken for a busy second owner.
        value=OBJECT+0x78; memcpy(second+0x70,&value,8);
        assert(runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==2 && pins==0 && word64(object+0x78)==0);
        guard_enabled=0;
        assert(!runtime_heap_guard_batch(batch_visit,NULL));
        assert(callbacks==2 && pins==0);
    } else if (!strcmp(argv[1],"lifetime")) {
        lifetime_maps=1; lifetime_external=1;
        class_functions[0]=ClassImage+0x48c80; class_functions[1]=ClassImage+0x493d0;
        field(0,ClassTable); field(0x70,OBJECT+0x78); field(0x78,0);
        field(0x40,ARENA); field(0x48,ARENA); field(0x58,1);
        field(0xb8,0); field(0xc8,External+0x10000);
        uint64_t node[13]={0};
        node[0]=ARENA; node[1]=OBJECT+0x38; node[2]=OBJECT+0x38; node[3]=OBJECT+0x38;
        node[11]=0x10000; node[12]=External+0x10000;
        memcpy(pools[0],node,sizeof(node));
        uint64_t header[2]={0,0x10003}; memcpy(external+0x10000,header,16);
        guard_watch=(HeapWatch){.image=ClassImage,.size=0x3000000,.read_host=fixture_host_read};
        guard_enabled=1;
        LifetimeContext state={.expected_base=External+0x10000,.mutex=OBJECT+0x78};
        runtime_heap_guard_visit(lifetime_visit,&state);
        assert(state.calls==1 && pins==0 && word64(object+0x78)==0);
        lifetime_external=0; /* Mapping is gone between visits: no old backing pointer is used. */
        runtime_heap_guard_visit(lifetime_visit,&state);
        assert(state.calls==1 && pins==0 && word64(object+0x78)==0);
        lifetime_external=1; change_class_on_pin=1;
        runtime_heap_guard_visit(lifetime_visit,&state);
        assert(state.calls==1 && pins==0 && word64(object+0x78)==0);
        change_class_on_pin=0;
        runtime_heap_guard_visit(lifetime_visit,&state); /* Destroyed/retyped heap is ignored. */
        assert(state.calls==1 && pins==0);
        field(0,ClassTable); field(0x70,OBJECT+0x90); field(0x90,0);
        field(0xc8,External); node[12]=External;
        memcpy(pools[0],node,sizeof(node)); memcpy(external,header,16);
        state.expected_base=External; state.mutex=OBJECT+0x90;
        runtime_heap_guard_visit(lifetime_visit,&state);
        assert(state.calls==2 && pins==0 && word64(object+0x78)==0 && word64(object+0x90)==0);
        table[3]=0;
        runtime_heap_guard_visit(lifetime_visit,&state);
        assert(state.calls==2 && pins==0); /* Removed table entry does not survive a visit. */
        table[3]=OBJECT;
        assert(runtime_heap_guard_batch(lifetime_batch_visit,&state));
        assert(state.calls==3 && pins==0 && word64(object+0x90)==0);
        lifetime_external=0;
        assert(!runtime_heap_guard_batch(lifetime_batch_visit,&state));
        assert(state.calls==3 && pins==0 && word64(object+0x90)==0);
        lifetime_external=1;
        class_functions[0]^=8;
        assert(!runtime_heap_guard_batch(lifetime_batch_visit,&state));
        assert(state.calls==3 && pins==0 && word64(object+0x90)==0);
    } else if (!strcmp(argv[1],"class")) {
        const uint64_t image_size=0x2000000;
        class_functions[0]=ClassImage+0x48c80; class_functions[1]=ClassImage+0x493d0;
        assert(runtime_heap_is_bpe_class(ClassImage,image_size,ClassTable,fixture_read,NULL));
        assert(!runtime_heap_is_bpe_class(ClassImage,image_size,ClassTable+8,fixture_read,NULL));
        class_functions[1]++;
        assert(!runtime_heap_is_bpe_class(ClassImage,image_size,ClassTable,fixture_read,NULL));
        class_functions[1]--; class_functions[0]++;
        assert(!runtime_heap_is_bpe_class(ClassImage,image_size,ClassTable,fixture_read,NULL));
        assert(!runtime_heap_is_bpe_class(ClassImage,0x10000,ClassTable,fixture_read,NULL));
        assert(!runtime_heap_is_bpe_class(UINTPTR_MAX-16,image_size,ClassTable,fixture_read,NULL));
        assert(!runtime_heap_is_bpe_class(ClassImage,image_size,ClassTable,NULL,NULL));
    } else if (!strcmp(argv[1],"kernel")) {
        unsigned char out[32];
        if (!host_read((uintptr_t)backings,out,sizeof(out)) && (errno==EPERM || errno==EACCES)) {
            fputs("process_vm_readv of this process is denied by the environment\n",stderr);
            return 77;
        }
        HeapWatch state={.read_host=host_read};
        memset(backings[0],0xab,16); memset(backings[1],0xcd,16);
        assert(watch_read(&state,Guest,out,32));
        for (size_t i=0;i<32;++i) assert(out[i]==(i<16 ? 0xcd : 0xab));
        inaccessible=1;
        assert(!watch_read(&state,Guest,out,32));
    } else return 2;
    puts("SotC heap inventory: PASS");
    return 0;
}
