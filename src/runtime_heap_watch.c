/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "runtime_heap_watch.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t word64(const unsigned char *p) {
    uint64_t value;
    memcpy(&value,p,sizeof(value));
    return value;
}

/* Page allocator descriptors and heap objects are different structures.
 * The EU 1.01 allocator at image+0x1a2f8 reads these descriptor fields. */
static void sample_page_pool(const unsigned char *object, RuntimeHeapSample *sample,
                             RuntimeHeapReader read, void *context) {
    /* The upstream heap watcher reads a u32 word count at +0x58. Not every
     * heap is a page pool; report counts only when all bounds and reads pass. */
    uint32_t words;
    memcpy(&words,object+0x58,sizeof(words));
    const uint64_t bitmap=word64(object+0x50), pages=word64(object+0x60);
    sample->candidate_bitmap=bitmap;
    sample->candidate_pages=pages;
    sample->candidate_words=words;
    sample->pool_status="word-count-invalid";
    if (!words || words>0x10000) return;
    sample->pool_status="page-count-invalid";
    if (!pages || pages>(uint64_t)words*64) return;
    sample->pool_status="bitmap-address-invalid";
    if (!bitmap || (bitmap&7) || bitmap>UINTPTR_MAX-(uint64_t)words*8) return;
    sample->pool_status="bitmap-unreadable";
    const uint64_t needed=(pages+63)/64;
    uint64_t free_pages=0;
    int valid=1;
    for (uint64_t offset=0;offset<needed;) {
        uint64_t chunk[512];
        const size_t n=(size_t)(needed-offset<512 ? needed-offset : 512);
        if (!read(context,(uintptr_t)(bitmap+offset*8),chunk,n*8)) { valid=0; break; }
        for (size_t i=0;i<n;++i) {
            const uint64_t remaining=pages-(offset+i)*64;
            uint64_t bits=chunk[i];
            if (remaining<64) bits&=(UINT64_C(1)<<remaining)-1;
            free_pages+=(uint64_t)__builtin_popcountll(bits);
        }
        offset+=n;
    }
    if (valid) {
        sample->pool_status="valid";
        sample->pool_valid=1;
        sample->pages=pages;
        sample->free_pages=free_pages;
    }
}

size_t runtime_heap_inventory(uintptr_t table, RuntimeHeapReader read, void *context,
                              RuntimeHeapSample *samples, size_t capacity) {
    uint64_t heaps[SOTC_HEAP_SLOTS];
    if (!read || !samples || !capacity || table>UINTPTR_MAX-sizeof(heaps) ||
        !read(context,table,heaps,sizeof(heaps))) return 0;
    size_t count=0;
    for (unsigned id=0;id<SOTC_HEAP_SLOTS && count<capacity;++id) {
        if (!heaps[id]) continue;
        RuntimeHeapSample *sample=&samples[count++];
        *sample=(RuntimeHeapSample){.id=id,.address=(uintptr_t)heaps[id],
                                    .pool_status="object-address-invalid"};
        /* Same user-address bound as the guard, with space for the whole object. */
        if (heaps[id]<0x10000 || heaps[id]>=(UINT64_C(1)<<40)-0x68 || (heaps[id]&7)) continue;
        sample->pool_status="object-unreadable";
        unsigned char object[0x68];
        if (!read(context,sample->address,object,sizeof(object))) continue;
        sample->readable=1;
        sample->class_address=word64(object);
        sample->base=word64(object+0x28);
        sample->bytes=word64(object+0x30);
        sample_page_pool(object,sample,read,context);
    }
    return count;
}

/* Initializer image+0x18c94 lays out three pool descriptors, stride 0xa0.
 * The image global is a pointer, not an inline descriptor or heap table. */
size_t runtime_page_pool_inventory(uintptr_t root_pointer, RuntimeHeapReader read, void *context,
                                   RuntimeHeapSample *samples, size_t capacity) {
    uint64_t root=0;
    if (!read || !samples || !capacity || root_pointer>UINTPTR_MAX-8 ||
        !read(context,root_pointer,&root,sizeof(root)) || root<0x10000 ||
        root>=(UINT64_C(1)<<40)-SOTC_PAGE_POOLS*0xa0 || (root&7)) return 0;
    const size_t count=capacity<SOTC_PAGE_POOLS ? capacity : SOTC_PAGE_POOLS;
    for (size_t i=0;i<count;++i) {
        RuntimeHeapSample *sample=&samples[i];
        *sample=(RuntimeHeapSample){.id=(unsigned)i,.address=(uintptr_t)(root+i*0xa0),
                                    .pool_status="object-unreadable"};
        unsigned char object[0x68];
        if (!read(context,sample->address,object,sizeof(object))) continue;
        sample->readable=1;
        sample_page_pool(object,sample,read,context);
    }
    return count;
}

int runtime_heap_is_bpe_class(uintptr_t image, uint64_t image_size, uint64_t class_address,
                              RuntimeHeapReader read, void *context) {
    const uint64_t vtable=0x1595b70, entries=0xa0;
    uint64_t functions[2];
    if (!read || !image || image_size>UINTPTR_MAX-image ||
        image_size<vtable+entries+sizeof(functions) || class_address!=image+vtable ||
        !read(context,(uintptr_t)class_address+entries,functions,sizeof(functions))) return 0;
    return functions[0]==image+0x48c80 && functions[1]==image+0x493d0;
}

/* Managed region list: generic allocation links descriptors at heap+0x38
 * (EU 1.01 +0x479ce); BPE obtains base/size from descriptor+0x60/+0x58
 * (+0x4898e). The external block path (+0x48a10) bypasses this list. */
int runtime_bpe_heap_regions(uintptr_t heap, RuntimeHeapReader read, void *context,
                             RuntimeHeapRegion *regions, size_t capacity,
                             size_t *count, const char **status) {
    if (count) *count=0;
    if (status) *status="arguments-invalid";
    if (!read || !regions || !capacity || !count || !status) return 0;
    *status="heap-unreadable";
    unsigned char header[0x60], after[0x28];
    if (heap<0x10000 || heap>=(UINT64_C(1)<<40)-sizeof(header) || (heap&7) ||
        !read(context,heap,header,sizeof(header))) return 0;
    uint32_t expected;
    memcpy(&expected,header+0x58,sizeof(expected));
    *status="capacity-exceeded";
    if (expected>capacity || expected>1024) return 0;
    const uint64_t sentinel=heap+0x38;
    uint64_t next=word64(header+0x48), previous=sentinel;
    for (uint32_t i=0;i<expected;++i) {
        *status="descriptor-address-invalid";
        if (next<0x10000 || next>=(UINT64_C(1)<<40)-0x68 || (next&7) || next==sentinel) return 0;
        unsigned char node[0x68];
        *status="descriptor-unreadable";
        if (!read(context,(uintptr_t)next,node,sizeof(node))) return 0;
        *status="links-inconsistent";
        if (word64(node)!=next || word64(node+8)!=previous || word64(node+0x18)!=sentinel) return 0;
        const uint64_t base=word64(node+0x60), bytes=word64(node+0x58);
        *status="range-invalid";
        if (base<0x100000000 || base>=(UINT64_C(1)<<40) || (base&0xffff) ||
            !bytes || (bytes&0xffff) || bytes>(UINT64_C(1)<<40)-base) return 0;
        for (uint32_t j=0;j<i;++j) {
            *status="ranges-overlap";
            if (base<regions[j].base+regions[j].bytes && regions[j].base<base+bytes) return 0;
        }
        regions[i]=(RuntimeHeapRegion){.descriptor=next,.base=base,.bytes=bytes};
        previous=next;
        next=word64(node+0x10);
    }
    *status="links-inconsistent";
    if (next!=sentinel || word64(header+0x40)!=previous) return 0;
    *status="list-changed";
    if (!read(context,heap+0x38,after,sizeof(after)) || memcmp(after,header+0x38,sizeof(after))) return 0;
    *status="valid";
    *count=expected;
    return 1;
}

/* Both managed (+0x489b8) and external (+0x48a36) paths link a dummy
 * header at the region base to heap+0xb8. External region ends are recovered
 * from the physical block chain, never from heap+0x28 or bytes in use. */
int runtime_bpe_all_regions(uintptr_t heap, RuntimeHeapReader read, void *context,
                            RuntimeHeapRegion *regions, size_t capacity,
                            size_t *count, const char **status) {
    RuntimeHeapRegion managed[1024];
    size_t managed_count=0;
    if (count) *count=0;
    if (status) *status="arguments-invalid";
    if (!regions || !capacity || !count || !status) return 0;
    if (!runtime_bpe_heap_regions(heap,read,context,managed,1024,&managed_count,status)) return 0;
    uint64_t head=0,after=0;
    *status="region-head-unreadable";
    if (!read(context,heap+0xb8,&head,8)) return 0;
    size_t n=0,matched=0;
    for (uint64_t base=head;base;) {
        *status="capacity-exceeded";
        if (n>=capacity || n>=1024) return 0;
        *status="region-address-invalid";
        if (base<0x100000000 || base>=(UINT64_C(1)<<40)-32 || (base&0xffff)) return 0;
        for (size_t j=0;j<n;++j) {
            *status="region-cycle";
            if (regions[j].base==base) return 0;
        }
        uint64_t header[2];
        *status="region-header-unreadable";
        if (!read(context,(uintptr_t)base,header,sizeof(header))) return 0;
        *status="region-header-invalid";
        if (header[1]!=3) return 0;
        uint64_t bytes=0,descriptor=0;
        for (size_t j=0;j<managed_count;++j) if (managed[j].base==base) {
            bytes=managed[j].bytes; descriptor=managed[j].descriptor; ++matched; break;
        }
        if (!bytes) {
            uint64_t block=base+16,previous=base;
            for (size_t step=0;step<4096;++step) {
                uint64_t words[2];
                *status="block-header-unreadable";
                if (block>(UINT64_C(1)<<40)-16 || !read(context,(uintptr_t)block,words,16)) return 0;
                *status="block-chain-invalid";
                if (words[0]!=previous) return 0;
                const uint64_t size=words[1]&~UINT64_C(7);
                if (!size) {
                    if (words[1]!=1) return 0;
                    bytes=block+16-base;
                    break;
                }
                if (size>UINT64_C(0x100000000) || size>(UINT64_C(1)<<40)-block-16) return 0;
                previous=block; block+=16+size;
            }
            *status="block-walk-limit";
            if (!bytes) return 0;
        }
        *status="range-invalid";
        if ((bytes&0xffff) || bytes>(UINT64_C(1)<<40)-base) return 0;
        for (size_t j=0;j<n;++j) {
            *status="ranges-overlap";
            if (base<regions[j].base+regions[j].bytes && regions[j].base<base+bytes) return 0;
        }
        regions[n++]=(RuntimeHeapRegion){.descriptor=descriptor,.base=base,.bytes=bytes};
        base=header[0];
    }
    *status="managed-region-missing";
    if (matched!=managed_count) return 0;
    *status="region-head-changed";
    if (!read(context,heap+0xb8,&after,8) || after!=head) return 0;
    *status="valid"; *count=n;
    return 1;
}

#ifndef _WIN32
#include <pthread.h>
#include <errno.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>

int runtime_memory_region(uintptr_t address, uintptr_t *start, uintptr_t *end, int *mapped);
const unsigned char *runtime_memory_backing_pointer(uintptr_t address);

typedef struct {
    uintptr_t image;
    uint64_t size;
    int (*read_host)(uintptr_t address,void *out,size_t size);
} HeapWatch;
static HeapWatch watch;
static int started;

static int host_read(uintptr_t address, void *out, size_t size) {
    if (!size || address>UINTPTR_MAX-size) return 0;
    struct iovec local={out,size}, remote={(void *)address,size};
    return process_vm_readv(getpid(),&local,1,&remote,1,0)==(ssize_t)size;
}

static int watch_read(void *context, uintptr_t address, void *out, size_t size) {
    const HeapWatch *state=context;
    int (*read_host)(uintptr_t,void *,size_t)=state->read_host ? state->read_host : host_read;
    if (!size || address>UINTPTR_MAX-size) return 0;
    if (address>=state->image && address-state->image<state->size &&
        size<=state->size-(address-state->image)) return read_host(address,out,size);
    /* Resolve each VMA separately; endpoint-only checks can cross an unmapped
     * hole. Read through the backing to avoid GPU page-tracking readbacks.
     * The kernel read fails safely even if a mapping disappears meanwhile. */
    while (size) {
        uintptr_t lo=0,hi=0;
        int mapped=0;
        if (!runtime_memory_region(address,&lo,&hi,&mapped) || !mapped ||
            address<lo || address>=hi) return 0;
        const unsigned char *backing=runtime_memory_backing_pointer(address);
        const size_t n=hi-address<size ? hi-address : size;
        if (!backing || !read_host((uintptr_t)backing,out,n)) return 0;
        address+=n;
        out=(unsigned char *)out+n;
        size-=n;
    }
    return 1;
}

static void *watch_main(void *unused) {
    (void)unused;
    pthread_setname_np(pthread_self(),"sotc:HeapWatch");
    for (;;) {
        struct timespec wait={.tv_sec=5};
        while (nanosleep(&wait,&wait) && errno==EINTR) {}
        RuntimeHeapSample samples[SOTC_HEAP_SLOTS];
        const size_t n=runtime_heap_inventory(watch.image+0x2dfaab0,watch_read,&watch,
                                             samples,SOTC_HEAP_SLOTS);
        flockfile(stderr);
        if (!n) fprintf(stderr,"SOTC HEAPS: table unavailable or no heaps yet (concurrent snapshot)\n");
        for (size_t i=0;i<n;++i) {
            const RuntimeHeapSample *s=&samples[i];
            fprintf(stderr,"SOTC HEAP %u @%#" PRIxPTR ": readable=%d class=%#" PRIx64
                    " base=%#" PRIx64 " bytes=%" PRIu64,s->id,s->address,s->readable,
                    s->class_address,s->base,s->bytes);
            if (s->pool_valid) fprintf(stderr," pages_free=%" PRIu64 "/%" PRIu64,
                                       s->free_pages,s->pages);
            else fprintf(stderr," page_pool=unavailable reason=%s candidate_bitmap=%#" PRIx64
                         " candidate_words=%" PRIu32 " candidate_pages=%" PRIu64,
                         s->pool_status,s->candidate_bitmap,s->candidate_words,s->candidate_pages);
            if (s->readable && runtime_heap_is_bpe_class(watch.image,watch.size,
                                                         s->class_address,watch_read,&watch))
            {
                RuntimeHeapRegion regions[1024];
                size_t count=0;
                const char *status;
                const int valid=runtime_bpe_all_regions(s->address,watch_read,&watch,regions,
                                                         1024,&count,&status);
                fprintf(stderr," bpe_class=verified regions_status=%s regions=%zu",status,count);
                if (valid) {
                    uint64_t total=0;
                    for (size_t j=0;j<count;++j) total+=regions[j].bytes;
                    fprintf(stderr," region_bytes=%" PRIu64,total);
                    for (size_t j=0;j<count && j<4;++j)
                        fprintf(stderr," region%zu=%#" PRIx64 "+%#" PRIx64,
                                j,regions[j].base,regions[j].bytes);
                }
            }
            fputc('\n',stderr);
        }
        RuntimeHeapSample pools[SOTC_PAGE_POOLS];
        const size_t pool_count=runtime_page_pool_inventory(watch.image+0x2dfca78,watch_read,
                                                            &watch,pools,SOTC_PAGE_POOLS);
        if (!pool_count) fprintf(stderr,"SOTC PAGE POOLS: root unavailable (concurrent snapshot)\n");
        for (size_t i=0;i<pool_count;++i) {
            const RuntimeHeapSample *s=&pools[i];
            fprintf(stderr,"SOTC PAGE POOL %u @%#" PRIxPTR ": readable=%d status=%s",
                    s->id,s->address,s->readable,s->pool_status);
            if (s->pool_valid) fprintf(stderr," pages_free=%" PRIu64 "/%" PRIu64,
                                      s->free_pages,s->pages);
            else fprintf(stderr," candidate_bitmap=%#" PRIx64 " candidate_words=%" PRIu32
                         " candidate_pages=%" PRIu64,s->candidate_bitmap,
                         s->candidate_words,s->candidate_pages);
            fputc('\n',stderr);
        }
        funlockfile(stderr);
    }
    return NULL;
}

int runtime_heap_watch_start(uintptr_t image, uint64_t image_size) {
    const char *enabled=getenv("SOTC_HEAP_WATCH");
    if (!enabled || strcmp(enabled,"1")) return 0;
    static const unsigned char expected[]={0x55,0x48,0x89,0xe5,0x41,0x57,0x41,0x56};
    static const unsigned char allocator_expected[]={0x41,0x8b,0x56,0x58,0x4d,0x8b,0x4e,0x50};
    unsigned char actual[sizeof(expected)], allocator_actual[sizeof(allocator_expected)];
    if (!image || image_size<0x2dfca78+8 ||
        image_size>UINTPTR_MAX-image || !host_read(image+0x495e0,actual,sizeof(actual)) ||
        memcmp(actual,expected,sizeof(expected)) ||
        !host_read(image+0x1a2f8,allocator_actual,sizeof(allocator_actual)) ||
        memcmp(allocator_actual,allocator_expected,sizeof(allocator_expected))) {
        fprintf(stderr,"SOTC HEAPS: image unavailable or unsupported; watcher not started\n");
        return 0;
    }
    if (__atomic_exchange_n(&started,1,__ATOMIC_ACQ_REL)) return 0;
    watch=(HeapWatch){.image=image,.size=image_size,.read_host=host_read};
    pthread_t thread;
    const int error=pthread_create(&thread,NULL,watch_main,NULL);
    if (error) {
        __atomic_store_n(&started,0,__ATOMIC_RELEASE);
        fprintf(stderr,"SOTC HEAPS: watcher could not start (%d)\n",error);
        return 0;
    }
    pthread_detach(thread);
    fprintf(stderr,"SOTC HEAPS: read-only Linux watcher enabled, interval 5 s\n");
    return 1;
}
#else
int runtime_heap_watch_start(uintptr_t image, uint64_t image_size) {
    (void)image; (void)image_size;
    return 0;
}
#endif
