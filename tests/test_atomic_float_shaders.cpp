// SPDX-License-Identifier: GPL-2.0-or-later
// Emit real shaders for validation of exclusive float-atomic fallback branches.
#include <filesystem>
#include <fstream>
#include "shader_recompiler/backend/spirv/emit_spirv.h"
#include "shader_recompiler/ir/ir_emitter.h"

extern "C" { volatile long long runtime_speculative_faults = 0; }

int main(int argc, char** argv) {
    using namespace Shader;
    const std::filesystem::path dir = argc > 1 ? argv[1] : ".";
    std::filesystem::create_directories(dir);
    for (bool native : {false, true}) {
        for (bool maximum : {false, true}) {
            Info info{};
            info.hw_stage = HwStage::Fragment;
            info.sw_stage = SwStage::Fragment;
            info.uses_buffer_atomic_float_min_max = true;
            info.buffers.push_back({.used_types = native ? IR::Type::F32 : IR::Type::U32,
                                    .is_written = true});
            info.loads.Set(IR::Attribute::FragCoord, 0);
            info.stores.Set(IR::Attribute::RenderTarget0, 0);
            RuntimeInfo runtime{};
            runtime.Initialize(info.hw_stage, info.sw_stage);
            runtime.hw.fs.color_buffers[0].num_format = AmdGpu::NumberFormat::Float;
            Common::ObjectPool<IR::Inst> pool;
            IR::Block block(pool);
            IR::IREmitter ir(block);
            ir.Prologue();
            const auto value = ir.GetAttribute(IR::Attribute::FragCoord, 0);
            const auto result = maximum
                ? ir.BufferAtomicFMax(ir.Imm32(0u), ir.Imm32(0u), value, {})
                : ir.BufferAtomicFMin(ir.Imm32(0u), ir.Imm32(0u), value, {});
            ir.SetAttribute(IR::Attribute::RenderTarget0, IR::F32{result}, 0);
            ir.Epilogue();
            IR::Program program(info);
            program.blocks.push_back(&block);
            program.syntax_list.push_back({.data = {.block = &block},
                                           .type = IR::AbstractSyntaxNode::Type::Block});
            program.syntax_list.push_back({.type = IR::AbstractSyntaxNode::Type::Return});
            Profile profile{};
            profile.supported_spirv = 0x00010600;
            profile.supports_buffer_fp32_atomic_min_max = native;
            Backend::Bindings bindings{};
            const auto code = Backend::SPIRV::EmitSPIRV(profile, runtime, program, bindings);
            const auto path = dir / (std::string(maximum ? "max" : "min") +
                                    (native ? "-native.spv" : "-fallback.spv"));
            std::ofstream out(path, std::ios::binary);
            out.write(reinterpret_cast<const char*>(code.data()), code.size() * sizeof(u32));
            if (!out) return 1;
        }
    }
}
