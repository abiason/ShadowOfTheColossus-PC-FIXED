// Regression test: real shader-info visitor must detect FP64 without pack/unpack.
#include <cstdio>
#include <csetjmp>
// Runtime state required when loading libbbgpu; no runtime services are used.
extern "C" {
thread_local sigjmp_buf* runtime_fault_recover = nullptr;
unsigned long long runtime_disabled_optimizations = 0;
volatile long long runtime_speculative_faults = 0;
}
#include "shader_recompiler/info.h"
#include "shader_recompiler/ir/microinstruction.h"
namespace Shader::Optimization { void Visit(Info&, const IR::Inst&); }
int main() {
    using Shader::IR::Opcode;
    const Opcode fp64[] = {
        Opcode::FPAbs64,
        Opcode::FPAdd64,
        Opcode::FPFma64,
        Opcode::FPMax64,
        Opcode::FPMin64,
        Opcode::FPMul64,
        Opcode::FPDiv64,
        Opcode::FPNeg64,
        Opcode::FPRecip64,
        Opcode::FPRecipSqrt64,
        Opcode::FPSaturate64,
        Opcode::FPClamp64,
        Opcode::FPRoundEven64,
        Opcode::FPFloor64,
        Opcode::FPCeil64,
        Opcode::FPTrunc64,
        Opcode::FPFract64,
        Opcode::FPFrexpSig64,
        Opcode::FPFrexpExp64,
        Opcode::FPOrdEqual64,
        Opcode::FPUnordEqual64,
        Opcode::FPOrdNotEqual64,
        Opcode::FPUnordNotEqual64,
        Opcode::FPOrdLessThan64,
        Opcode::FPUnordLessThan64,
        Opcode::FPOrdGreaterThan64,
        Opcode::FPUnordGreaterThan64,
        Opcode::FPOrdLessThanEqual64,
        Opcode::FPUnordLessThanEqual64,
        Opcode::FPOrdGreaterThanEqual64,
        Opcode::FPUnordGreaterThanEqual64,
        Opcode::FPIsNan64,
        Opcode::FPIsInf64,
        Opcode::ConvertS32F64,
        Opcode::ConvertF32F64,
        Opcode::ConvertF64F32,
        Opcode::ConvertF64S32,
        Opcode::ConvertF64U32,
        Opcode::PackDouble2x32,
        Opcode::UnpackDouble2x32,
    };
    for (const auto opcode : fp64) {
        Shader::Info info{};
        Shader::IR::Inst inst(opcode, 0);
        Shader::Optimization::Visit(info, inst);
        if (!info.uses_fp64) {
            std::fprintf(stderr, "FP64 opcode missed: %u\n", unsigned(opcode));
            return 1;
        }
    }
    for (const auto opcode : {Opcode::FPAdd32, Opcode::FPMul32, Opcode::IAdd32}) {
        Shader::Info info{};
        Shader::IR::Inst inst(opcode, 0);
        Shader::Optimization::Visit(info, inst);
        if (info.uses_fp64) return 2;
    }
    std::puts("FP64 detection: 40 positive and 3 negative cases passed");
}
