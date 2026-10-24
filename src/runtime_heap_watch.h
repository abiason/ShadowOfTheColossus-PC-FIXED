/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef SOTC_RUNTIME_HEAP_WATCH_H
#define SOTC_RUNTIME_HEAP_WATCH_H
#include <stddef.h>
#include <stdint.h>

enum { SOTC_HEAP_SLOTS = 48, SOTC_PAGE_POOLS = 3 };
typedef int (*RuntimeHeapReader)(void *context, uintptr_t address, void *out, size_t size);
typedef struct {
    unsigned id;
    uintptr_t address;
    uint64_t class_address, base, bytes, pages, free_pages;
    /* Candidate fields, not validated pool metadata until pool_valid is set. */
    uint64_t candidate_bitmap, candidate_pages;
    uint32_t candidate_words;
    const char *pool_status;
    int readable, pool_valid;
} RuntimeHeapSample;

/* Read-only, bounded snapshots of the EU 1.01 heap table. A failed read is not
 * interpreted as an empty pool. Concurrent samples are diagnostic, not atomic. */
size_t runtime_heap_inventory(uintptr_t table, RuntimeHeapReader read, void *context,
                              RuntimeHeapSample *samples, size_t capacity);
/* EU 1.01 page allocator root (image+0x2dfca78), separate from heap objects. */
size_t runtime_page_pool_inventory(uintptr_t root_pointer, RuntimeHeapReader read, void *context,
                                   RuntimeHeapSample *samples, size_t capacity);
/* EU 1.01 BPE class identity: vtable location plus allocation/free entries.
 * Classification only; it does not establish a contiguous guarded range. */
int runtime_heap_is_bpe_class(uintptr_t image, uint64_t image_size, uint64_t class_address,
                              RuntimeHeapReader read, void *context);
typedef struct {
    uint64_t descriptor, base, bytes;
} RuntimeHeapRegion;
/* Returns only complete, structurally consistent managed-descriptor lists.
 * Externally supplied blocks may exist outside this list; an empty list does
 * not establish an empty heap. Concurrent changes may occur after sampling.
 * Caller must verify the BPE class. */
int runtime_bpe_heap_regions(uintptr_t heap, RuntimeHeapReader read, void *context,
                             RuntimeHeapRegion *regions, size_t capacity,
                             size_t *count, const char **status);
/* Includes external blocks linked at heap+0xb8; rejects incomplete walks. */
int runtime_bpe_all_regions(uintptr_t heap, RuntimeHeapReader read, void *context,
                            RuntimeHeapRegion *regions, size_t capacity,
                            size_t *count, const char **status);
/* Linux: optional SOTC_HEAP_WATCH=1 monitor; disabled by default. */
int runtime_heap_watch_start(uintptr_t image, uint64_t image_size);
#endif
