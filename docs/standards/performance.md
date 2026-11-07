# Performance and benchmarking

Performance claims are measurements with a method. Anything else is a guess and is labelled
**[Speculative]**.

## Rules

1. **Never claim Fyrkat is faster, smaller or better than another operating system** without
   comparable measurements: same hardware, same workload, same configuration, same
   measurement method, with the other system tuned fairly. Without those, say what was measured
   and make no comparison.
2. **State what was measured.** Report the metric, the unit, the workload, and what the
   workload leaves out.
3. **Emulators measure the emulator.** QEMU timings say little about hardware performance.
   Report them only as a development-loop measurement, such as boot latency of the test
   harness, and say so.
4. **Report the environment**: hardware model, CPU, firmware, host OS, QEMU and compiler
   versions, build profile, accelerator, and the commit.
5. **Repeat and show spread.** Run enough times to show variance, give the median with the
   minimum and maximum (or percentiles), and say how many runs. Discard nothing silently.
6. **Warm up and isolate.** Separate cold from warm runs. Control frequency scaling and
   background load where the platform allows, and note where it does not.
7. **Measure before optimising.** An optimisation PR includes before and after numbers from
   the same method.

## Reproducibility

A benchmark lives in the repository with its script and the exact command. Results are
stored with the metadata from rule 4. The numbers in a document trace to a stored result
labelled **[Measured]**.

## Regressions

A suspected performance regression is reported with the performance regression issue form. It
needs a baseline commit, a regressed commit and the measurement method. CI does not gate on
timing, because shared runners are too noisy to give a trustworthy threshold.
