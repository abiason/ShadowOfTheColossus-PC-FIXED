#define _GNU_SOURCE
#include <assert.h>
#include <signal.h>
#include <sys/mman.h>
#include "fault_snapshot.h"

static uint64_t object[16], table[128], stack_words[32];
static FaultSnapshot captured;
static void capture_signal(int sig) {
    (void)sig;
    fault_snapshot(&captured, (uintptr_t)object, (uintptr_t)table, 128,
                    (uintptr_t)stack_words);
}

int main(void) {
    object[10] = 0x1234;
    table[2] = 0x81;
    table[100] = 0xf;
    stack_words[1] = 0xabcd;
    struct sigaction action = {.sa_handler = capture_signal};
    sigemptyset(&action.sa_mask);
    assert(sigaction(SIGUSR1, &action, NULL) == 0);
    assert(raise(SIGUSR1) == 0);
    assert(captured.object_bytes == sizeof(object) && captured.object[10] == 0x1234);
    assert(captured.stack_bytes == sizeof(stack_words) && captured.stack[1] == 0xabcd);
    assert(captured.table_bytes == sizeof(table));
    assert(captured.nonzero_words == 2 && captured.set_bits == 6);
    assert(captured.first_nonzero_word == 2 && captured.table_prefix[2] == 0x81);

    FaultSnapshot invalid;
    fault_snapshot(&invalid, 0, 0x2000001000213270ULL, 8, 0);
    assert(invalid.object_bytes == -1 && invalid.object_error == EFAULT);
    assert(invalid.stack_bytes == -1 && invalid.stack_error == EFAULT);
    assert(invalid.table_bytes == 0 && invalid.table_error == EFAULT);

    const size_t page = (size_t)sysconf(_SC_PAGESIZE);
    unsigned char *p = mmap(NULL, page * 2, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(p != MAP_FAILED);
    memset(p, 0xff, page);
    assert(mprotect(p + page, page, PROT_NONE) == 0);
    fault_snapshot(&invalid, (uintptr_t)object, (uintptr_t)(p + page - 16), 8,
                    (uintptr_t)stack_words);
    assert(invalid.table_bytes == 16 && invalid.set_bits == 128);
    assert(munmap(p, page * 2) == 0);

    static uint64_t large[8192];
    large[8191] = 1;
    fault_snapshot(&invalid, (uintptr_t)object, (uintptr_t)large, UINT64_MAX,
                    (uintptr_t)stack_words);
    assert(invalid.table_truncated && invalid.table_bytes == sizeof(large));
    assert(invalid.first_nonzero_word == 8191 && invalid.set_bits == 1);
    fault_snapshot(&invalid, (uintptr_t)object, UINTPTR_MAX - 3, 1,
                    (uintptr_t)stack_words);
    assert(invalid.table_error == EOVERFLOW && invalid.table_bytes == 0);
}
