# Testing strategy

Tests exist to find defects and to prove that behaviour did not regress. Coverage percentage
is **not a target**: a high number says code ran, not that it was checked. Tests are judged by
whether they would fail if the code were wrong.

An emulator pass does not prove hardware correctness. QEMU models a machine; real devices
differ in timing, errata, cache behaviour and failure modes. A result obtained under QEMU is
labelled as such, and a hardware claim needs a hardware run.

## Layers

| Layer | Purpose | Status today |
|---|---|---|
| Host unit tests | Pure logic, run by `cargo nextest` on the host | In use, for `xtask` |
| Property tests | Invariants over generated inputs, for parsers, allocators and data structures | Not yet. Adding a property-testing crate is a dependency decision. |
| QEMU integration | Boot and run real target code under emulation | In use: `cargo xtask boot` runs `tests/boot-smoke` on AArch64 and x86-64. It checks the toolchain and firmware pipeline, not a kernel. |
| Fault injection | Exercise failure paths: allocation failure, device errors, malformed messages | Not yet. Needed once components with failure paths exist. |
| Fuzzing | Hostile input to anything that parses untrusted data | Not yet. See omissions. |
| Hardware in the loop | Run on physical boards from CI or a lab | Not yet. No hardware is owned or configured. |
| Formal verification | Proofs about selected components or the kernel | Not yet. Scope depends on [ADR 0004](../adr/0004-kernel-foundation.md). |

## Rules

- A bug fix starts with a test that fails for the right reason.
- Test behaviour through public interfaces. Test error paths, not only success.
- Tests are deterministic. No sleeps for synchronisation, no dependence on network or wall
  clock, except where the thing under test is that boundary.
- QEMU tests have timeouts and fail on a missing success marker. Silence is a failure.
- A check that is shown never to fail is removed or fixed. When a new check is added, show it
  failing once.

## Deliberately omitted tools

Each tool below was left out on purpose. Add it when its trigger is met, in a PR that states
what it will check.

| Tool | Why omitted now | Trigger to add |
|---|---|---|
| `cargo-audit` | `cargo-deny` already checks RustSec advisories, so a second tool adds noise. | `cargo-deny` stops meeting a need, for example scanning shipped binaries for vulnerable dependencies. |
| `cargo-llvm-cov` | Coverage is not a target, and there is no product code to measure. | Product code with a test suite exists, and a review needs to know which paths are never exercised. It is then an investigation aid, not a gate. |
| `cargo-fuzz` | There is no parser or decoder of untrusted input. | The first such code lands: IPC or message decoding, an image or ELF loader, a filesystem or network parser. |
| Miri CI job | There is no unsafe product code that can run on the host. Miri cannot run hardware access or assembly. | The first unsafe product code that is host-testable, such as an allocator or an intrusive data structure. It needs a pinned nightly; see [toolchain](toolchain.md). |
