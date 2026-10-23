/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Include the implementation so the actual host/backing adapter is exercised too. */
#include "../src/runtime_heap_watch.c"
#include <assert.h>

enum { TABLE=0x20000, OBJECT=0x30000, BITMAP=0x40000, ARENA=0x50000 };
static uint64_t table[SOTC_HEAP_SLOTS], bitmap[1024];
static unsigned char object[0x68], pools[SOTC_PAGE_POOLS][0xa0];
static int read_calls, fail_second_chunk;
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
    if (!source) return 0;
    memcpy(out,source,size);
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

/* Synthetic guest mappings deliberately have separate physical backing arrays. */
static const uintptr_t Guest=UINT64_C(0x100000000);
static unsigned char backings[2][16];
static int hole, inaccessible;
static int fixture_host_read(uintptr_t address,void *out,size_t size) {
    const uintptr_t base=(uintptr_t)backings;
    if (address<base || address-base>=sizeof(backings) ||
        size>sizeof(backings)-(address-base)) return 0;
    memcpy(out,(const void *)address,size);
    return 1;
}
int runtime_memory_region(uintptr_t address,uintptr_t *start,uintptr_t *end,int *mapped) {
    if (address<Guest || address-Guest>=32) return 0;
    const size_t region=(address-Guest)/16;
    *start=Guest+region*16; *end=*start+16;
    *mapped=!(hole && region==1);
    return 1;
}
const unsigned char *runtime_memory_backing_pointer(uintptr_t address) {
    if (inaccessible) return (const unsigned char *)1;
    if (address<Guest || address-Guest>=32) return NULL;
    /* Reverse the physical order to rule out a single memcpy across guest VMAs. */
    const size_t region=(address-Guest)/16;
    return backings[1-region]+(address-Guest)%16;
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
        hole=1;
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
