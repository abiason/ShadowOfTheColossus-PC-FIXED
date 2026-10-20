// SPDX-License-Identifier: GPL-2.0-or-later
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <fstream>
#include <iostream>
#include <queue>
#include <thread>
#include "video_core/shader_binary_store.h"

using Store = Storage::ShaderBinaryStore;
using Result = Store::Result;

static std::vector<u8> Read(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(file), {}};
}

int main(int argc, char** argv) {
    assert(argc == 2);
    const auto root = std::filesystem::path(argv[1]);
    assert(!std::filesystem::exists(root));
    std::filesystem::create_directories(root);
    const auto path = root / "program_0.spv";
    const std::vector<u32> original{0x07230203, 1, 2, 3};
    const std::vector<u32> other{0x07230203, 1, 2, 4};
    Store store;
    std::queue<std::packaged_task<void()>> queue;
    std::mutex mutex;
    std::condition_variable cv;
    bool release = false;
    std::atomic<unsigned> failures{};
    const auto report = [&] { ++failures; };
    const auto submit = [&](std::packaged_task<void()>&& task) {
        std::scoped_lock lock{mutex};
        queue.emplace(std::move(task));
        return true;
    };

    // Deliberately hold the worker before it can publish the accepted binary.
    auto worker = std::thread([&] {
        std::packaged_task<void()> task;
        {
            std::unique_lock lock{mutex};
            cv.wait(lock, [&] { return release; });
            assert(queue.size() == 1);
            task = std::move(queue.front());
            queue.pop();
        }
        task();
        task.get_future().get();
    });
    assert(store.Save(path, std::vector(original), submit, report) == Result::Accepted);
    assert(!std::filesystem::exists(path));
    std::thread conflicting([&] {
        assert(store.Save(path, std::vector(other), submit, report) == Result::Conflict);
    });
    std::thread identical([&] {
        assert(store.Save(path, std::vector(original), submit, report) == Result::Accepted);
    });
    conflicting.join();
    identical.join();
    {
        std::scoped_lock lock{mutex};
        assert(queue.size() == 1);
        release = true;
    }
    cv.notify_one();
    worker.join();
    const auto saved = Read(path);
    assert(saved.size() == original.size() * sizeof(u32));
    assert(std::memcmp(saved.data(), original.data(), saved.size()) == 0);

    // A new session must compare with disk, accepting identical bytes without rewriting them.
    Store reopened;
    assert(reopened.Save(path, std::vector(other), submit, report) == Result::Conflict);
    assert(reopened.Save(path, {1}, submit, report) == Result::Conflict);
    assert(reopened.Save(path, std::vector(original), submit, report) == Result::Accepted);
    assert(queue.empty());
    assert(Read(path) == saved);

    const auto drain = [&] {
        auto task = std::move(queue.front());
        queue.pop();
        task();
        task.get_future().get();
    };
    // Shutdown rejecting a request must release the reservation, allowing a later retry.
    const auto retry = root / "retry.spv";
    assert(store.Save(retry, std::vector(original),
                      [](std::packaged_task<void()>&&) { return false; }, report) ==
           Result::Unavailable);
    assert(store.Save(retry, std::vector(other), submit, report) == Result::Accepted);
    drain();
    assert(Read(retry) != saved);

    // Publication failure must also release the reservation rather than poison future retries.
    const auto missing = root / "missing" / "retry.spv";
    assert(store.Save(missing, std::vector(original), submit, report) == Result::Accepted);
    drain();
    assert(failures == 1);
    std::filesystem::create_directory(missing.parent_path());
    assert(store.Save(missing, std::vector(other), submit, report) == Result::Accepted);
    drain();
    assert(std::filesystem::is_regular_file(missing));

    // Unreadable/non-file destinations are unavailable, never permission to overwrite.
    assert(store.Save(root, std::vector(original), submit, report) == Result::Unavailable);
    assert(queue.empty());
    assert(Read(path) == saved);
    std::cout << "Shader binary store: pending/disk collisions, concurrency and retries passed\n";
}
