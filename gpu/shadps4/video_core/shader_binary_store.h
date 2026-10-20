// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cstring>
#include <fstream>
#include <functional>
#include <future>
#include <map>
#include <memory>
#include <mutex>
#include <vector>
#include "common/cache_file.h"
#include "common/scope_exit.h"
#include "common/types.h"

namespace Storage {

// Shader names contain session-local permutation indices. Reserve pending bytes as well as
// checking disk, so a second compilation cannot replace a different permutation in the IO queue.
class ShaderBinaryStore {
public:
    enum class Result { Accepted, Conflict, Unavailable };

    template <typename Submit, typename ReportFailure>
    Result Save(const std::filesystem::path& path, std::vector<u32>&& words,
                Submit&& submit, ReportFailure report_failure) {
        std::scoped_lock lock{mutex};
        if (const auto it = pending.find(path); it != pending.end()) {
            return *it->second == words ? Result::Accepted : Result::Conflict;
        }

        std::error_code error;
        const bool exists = std::filesystem::exists(path, error);
        if (error) return Result::Unavailable;
        if (exists) {
            const auto size = std::filesystem::file_size(path, error);
            if (error) return Result::Unavailable;
            if (size != words.size() * sizeof(u32)) return Result::Conflict;
            std::vector<u32> stored(words.size());
            std::ifstream file(path, std::ios::binary);
            if (!file.read(reinterpret_cast<char*>(stored.data()), size)) {
                return Result::Unavailable;
            }
            return stored == words ? Result::Accepted : Result::Conflict;
        }

        auto data = std::make_shared<std::vector<u32>>(std::move(words));
        pending.emplace(path, data);
        bool queued = false;
        SCOPE_EXIT { if (!queued) pending.erase(path); };
        queued = submit(std::packaged_task<void()>{[this, path, data, report_failure] {
            bool published = false;
            {
                std::scoped_lock write_lock{mutex};
                SCOPE_EXIT { pending.erase(path); };
                published = Common::FS::WriteCacheFile(
                    path, {reinterpret_cast<const u8*>(data->data()), data->size() * sizeof(u32)});
            }
            if (!published) report_failure();
        }});
        return queued ? Result::Accepted : Result::Unavailable;
    }

private:
    std::mutex mutex;
    std::map<std::filesystem::path, std::shared_ptr<std::vector<u32>>> pending;
};

} // namespace Storage
