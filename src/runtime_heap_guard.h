/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef SOTC_RUNTIME_HEAP_GUARD_H
#define SOTC_RUNTIME_HEAP_GUARD_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { RUNTIME_GUARD_REGION_CACHED = 1 };
typedef struct { uint64_t base, bytes; uint32_t flags; } RuntimeGuardRegion;
typedef int (*RuntimeGuardRead)(void *, uintptr_t, void *, size_t);
typedef void (*RuntimeGuardVisit)(void *, uintptr_t, const RuntimeGuardRegion *, size_t,
                                  RuntimeGuardRead, void *);
void runtime_heap_guard_start(uintptr_t image, uint64_t size);
/* Callback runs with VMA read pin and the heap's allocator lock held.
 * Busy, uninitialized, unreadable or unstable heaps are skipped; never spins. */
void runtime_heap_guard_visit(RuntimeGuardVisit visit, void *context);
#ifdef __cplusplus
}
#endif
#endif
