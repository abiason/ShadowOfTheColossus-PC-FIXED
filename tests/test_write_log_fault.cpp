// Linux diagnostic regression: invalid fault-time RAX must not cause another fault.
#include <cassert>
#include <cstdlib>
#include <cstdint>
#include <ucontext.h>
#include "bbport_write_log.h"

int main() {
    assert(setenv("BB_WRITE_LOG", "1", 1) == 0);
    std::uint64_t table[16]{};
    BbWriteLog::Note(reinterpret_cast<std::uintptr_t>(table), table, sizeof(table),
                      BbWriteLog::Backing);
    ucontext_t uc{};
    uc.uc_mcontext.gregs[REG_RAX] = 0x8000000000000000ULL;
    uc.uc_mcontext.gregs[REG_R8] = 0x3ffffffffffffffULL;
    uc.uc_mcontext.gregs[REG_R9] = reinterpret_cast<std::uintptr_t>(table);
    bbgpu_dump_guest_writes(&uc);
}
