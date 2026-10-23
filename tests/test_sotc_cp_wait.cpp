// SPDX-License-Identifier: GPL-2.0-or-later
// Exercise the real Liverpool worker with PM4 packets, without a Vulkan device.
#include <atomic>
#include <array>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <memory>
#include <sched.h>
#include <string_view>
#include <sys/syscall.h>
#include <thread>
#include <unistd.h>
#include <vector>
#include "core/libraries/videoout/driver.h"
#include "video_core/amdgpu/liverpool.h"
#include "video_core/amdgpu/pm4_cmds.h"

namespace {
std::atomic<long> command_tid{};
std::atomic<unsigned> yields{}, yield_errors{};
using namespace std::chrono_literals;
bool until(auto&& predicate) {
    const auto deadline = std::chrono::steady_clock::now() + 2s;
    while (!predicate()) {
        if (std::chrono::steady_clock::now() >= deadline) return false;
        std::this_thread::sleep_for(100us);
    }
    return true;
}
}

// Interpose the actual scheduler call made by libbbgpu's std::this_thread::yield.
// Calls from the fixture thread do not count; no production counters are added.
extern "C" int sched_yield() noexcept {
    const auto result = syscall(SYS_sched_yield);
    if (syscall(SYS_gettid) == command_tid.load(std::memory_order_relaxed)) {
        if (result == 0) yields.fetch_add(1, std::memory_order_relaxed);
        else yield_errors.fetch_add(1, std::memory_order_relaxed);
    }
    return static_cast<int>(result);
}
extern "C" {
volatile long long runtime_speculative_faults = 0;
int runtime_sotc_neo() { return 0; }
}

int main(int argc, char** argv) {
    using namespace AmdGpu;
    assert(argc >= 3);
    const std::string_view mode = argv[1];
    const bool enabled = std::string_view(argv[2]) == "on";
    if (argc > 3 && std::string_view(argv[3]) == "one-cpu") {
        cpu_set_t available, selected;
        CPU_ZERO(&available); CPU_ZERO(&selected);
        if (sched_getaffinity(0, sizeof(available), &available) != 0) return 77;
        for (int i = 0; i < CPU_SETSIZE; ++i) {
            if (CPU_ISSET(i, &available)) { CPU_SET(i, &selected); break; }
        }
        if (sched_setaffinity(0, sizeof(selected), &selected) != 0) return 77;
    }
    Libraries::VideoOut::VideoOutPort port{};
    auto cp = std::make_unique<Liverpool>();
    cp->SetVoPort(&port);
    cp->SendCommand<true>([] { command_tid.store(syscall(SYS_gettid), std::memory_order_release); });

    // Map queue 1, finish an empty submission, then leave it empty. This exercises
    // idle rounds when either queue 0 or queue 1 has no task to resume.
    u32 read_position = 0;
    cp->SendCommand<true>([&] {
        cp->asc_queues.insert(Liverpool::AscQueueInfo{
            .map_addr = 0, .read_addr = &read_position, .ring_size_dw = 1024,
            .pipe_id = 0, .tmp_packet = {}, .tmp_dwords = 0,
        });
    });
    cp->SubmitAsc(1, {});
    cp->WaitGpuIdle();
    yields.store(0);

    if (mode == "active") {
        std::vector<u32> packets;
        for (unsigned i = 0; i < 2000; ++i) {
            packets.push_back(PM4Type3Header(PM4ItOpcode::Nop, 0).raw);
            packets.push_back(0);
        }
        cp->SubmitGfx(packets, {});
        cp->WaitGpuIdle();
        assert(yields.load() == 0); // Real packet work must not request scheduler yields.
    } else {
        constexpr u32 reg = 5, ready = 7;
        const std::array<u32, 7> wait = {
            PM4Type3Header(PM4ItOpcode::WaitRegMem, 5).raw,
            3, reg, 0, ready, 0xffffffffu, 10,
        };
        const auto waits_before = SotcStats::sync_events[7].load();
        if (mode == "compute") cp->SubmitAsc(1, wait);
        else cp->SubmitGfx(wait, {});
        assert(until([&] { return SotcStats::sync_events[7].load() > waits_before; }));
        if (enabled) {
            assert(until([] { return yields.load() > 0; }));
        } else {
            std::this_thread::sleep_for(20ms);
            assert(yields.load() == 0);
        }
        bool callback_ran = false;
        cp->SendCommand<true>([&] {
            cp->regs.reg_array[reg] = ready;
            callback_ran = true;
        });
        cp->WaitGpuIdle();
        assert(callback_ran && cp->IsGpuIdle());
        if (mode == "compute") assert(read_position == wait.size());
    }
    assert(yield_errors.load() == 0);
    std::printf("Liverpool %s: completed; scheduler yields=%u\n", argv[1], yields.load());
}
