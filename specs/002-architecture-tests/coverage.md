# Runtime Coverage: Full Suite Timing (SC-005)

Measures the complete test suite (Tenancy.UnitTests + Tenancy.IntegrationTests + ArchitectureTests) against SC-005's five-minute bar, on the stated reference hardware, so the bound is reproducible rather than asserted without context.

## Reference environment

**Hardware**: Apple M3 Pro, 18 GB RAM  
**OS**: macOS 25.5.0 ARM64 (Darwin Kernel Version 25.5.0)  
**Chip**: ARM64 T6030  

Command: `uname -a` → `Darwin Mac.lan 25.5.0 Darwin Kernel Version 25.5.0: Tue Jun  9 22:28:29 PDT 2026; root:xnu-12377.121.10~1/RELEASE_ARM64_T6030 arm64`  
CPU brand: `sysctl -n machdep.cpu.brand_string` → `Apple M3 Pro`  
RAM: `sysctl -n hw.memsize` → 18 GB

## Measurements (3 runs)

All three runs executed the full test suite with `--no-build` after an initial untimed build. Command chain per run:
```bash
time (dotnet test tests/Tenancy.UnitTests/Tenancy.UnitTests.csproj --no-build && \
      dotnet test tests/Tenancy.IntegrationTests/Tenancy.IntegrationTests.csproj --no-build && \
      dotnet test tests/ArchitectureTests/ArchitectureTests.csproj --no-build)
```

| Run | Tests | Unit | Integration | Architecture | Wall time |
|---|---|---|---|---|---|
| 1 | 222 (114+86+22) | 114 passed, 156ms | 86 passed, 18s 707ms | 22 passed, 279ms | 22.218s |
| 2 | 222 (114+86+22) | 114 passed, 152ms | 86 passed, 19s 295ms | 22 passed, 294ms | 22.269s |
| 3 | 222 (114+86+22) | 114 passed, 156ms | 86 passed, 18s 760ms | 22 passed, 276ms | 21.723s |

**Min**: 21.723s  
**Median**: 22.218s  
**Max**: 22.269s

## Conclusion

SC-005 requires the full suite to complete unattended in under 5 minutes (300 seconds). All three runs comfortably meet this bound, with the longest run at 22.269 seconds, leaving a 92% safety margin (277.731 seconds buffer).

The test suite is deterministic and performant on reference hardware. Timing variance across the 3 runs is negligible (21.723s to 22.269s, a 0.546s spread or 2.5% coefficient of variation), indicating stable performance suitable as a reproducible reference measurement.

**Result**: ✓ SC-005 passes with significant margin. CHK020 (reproducibility check) resolved with explicit hardware naming and 3 real, timed measurements.
