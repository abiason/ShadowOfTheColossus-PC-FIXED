/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef SOTC_RUNTIME_HEAP_WATCH_H
#define SOTC_RUNTIME_HEAP_WATCH_H
#include <stddef.h>
#include <stdint.h>

enum { SOTC_HEAP_SLOTS = 48 };
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
/* Linux: optional SOTC_HEAP_WATCH=1 monitor; disabled by default. */
int runtime_heap_watch_start(uintptr_t image, uint64_t image_size);
#endif
