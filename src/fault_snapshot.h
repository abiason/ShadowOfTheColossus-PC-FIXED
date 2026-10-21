/* Bounded Linux fatal-fault diagnostics; no direct reads of guest pointers. */
#ifndef FAULT_SNAPSHOT_H
#define FAULT_SNAPSHOT_H
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/uio.h>
#include <unistd.h>

typedef struct {
    uint64_t object[16], table_prefix[16], stack[32];
    ssize_t object_bytes, stack_bytes;
    int object_error, stack_error, table_error;
    size_t table_bytes, nonzero_words, set_bits;
    uint64_t first_nonzero_word;
    int table_truncated;
} FaultSnapshot;

static inline ssize_t fault_read_memory(uintptr_t address, void *out, size_t size) {
    struct iovec local = {out, size}, remote = {(void *)address, size};
    return process_vm_readv(getpid(), &local, 1, &remote, 1, 0);
}

static inline void fault_snapshot(FaultSnapshot *out, uintptr_t object, uintptr_t table,
                                   uint64_t words, uintptr_t stack) {
    memset(out, 0, sizeof(*out));
    out->first_nonzero_word = UINT64_MAX;
    out->object_bytes = fault_read_memory(object, out->object, sizeof(out->object));
    if (out->object_bytes < 0) out->object_error = errno;
    out->stack_bytes = fault_read_memory(stack, out->stack, sizeof(out->stack));
    if (out->stack_bytes < 0) out->stack_error = errno;
    const size_t limit = words > 8192 ? 8192 : (size_t)words;
    out->table_truncated = words > 8192;
    uint64_t chunk[64];
    for (size_t first = 0; first < limit;) {
        const size_t count = limit - first < 64 ? limit - first : 64;
        if (table > UINTPTR_MAX - first * sizeof(uint64_t) ||
            table + first * sizeof(uint64_t) > UINTPTR_MAX - count * sizeof(uint64_t)) {
            out->table_error = EOVERFLOW;
            break;
        }
        const ssize_t n = fault_read_memory(table + first * sizeof(uint64_t), chunk,
                                             count * sizeof(uint64_t));
        if (n < 0) { out->table_error = errno; break; }
        out->table_bytes += (size_t)n;
        for (size_t i = 0; i < (size_t)n / sizeof(uint64_t); ++i) {
            if (first + i < 16) out->table_prefix[first + i] = chunk[i];
            if (chunk[i]) {
                ++out->nonzero_words;
                out->set_bits += (size_t)__builtin_popcountll(chunk[i]);
                if (out->first_nonzero_word == UINT64_MAX) out->first_nonzero_word = first + i;
            }
        }
        if ((size_t)n != count * sizeof(uint64_t)) break;
        first += count;
    }
}
#endif
