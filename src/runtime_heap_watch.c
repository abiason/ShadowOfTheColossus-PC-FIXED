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
                fprintf(stderr," bpe_class=verified range=undetermined");
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
