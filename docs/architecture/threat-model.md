# Threat model

Initial version, 2026-11-07. **No mitigation here is implemented, because no system exists
yet.** This records what Fyrkat must defend against, so that designs can be tested against
it. It will change as the architecture is decided.

## Assets

| Asset | Why it matters |
|---|---|
| User data | Confidentiality and integrity are the primary purpose of the system |
| Keys and credentials | Compromise defeats other protections |
| Isolation between components | Everything else depends on it |
| System integrity | The system must run what its owner intends |
| Availability | A faulty component must not take the system down |
| Owner control | The owner, not a vendor, must control the system |
| Project integrity | Source, toolchain, CI and releases are themselves targets |

## Adversaries

| Adversary | Capability assumed |
|---|---|
| Malicious application | Runs arbitrary native code with whatever it was granted |
| Compromised service or driver | Fully controlled by the attacker, holding its capabilities |
| Malicious guest VM | Arbitrary code in a guest |
| Network attacker | Controls traffic, and sends malformed input to exposed services |
| Malicious peripheral | Attempts DMA, and malformed device responses |
| Device thief | Physical possession of a powered-off device |
| Supply chain attacker | Compromises a dependency, tool, action or update path |
| Compromised contributor or agent | Submits malicious changes, including AI-generated ones |

## Trust boundaries

1. Hardware and firmware, and everything above them.
2. Kernel and user mode.
3. Between user-mode components, including drivers.
4. Device DMA and system memory.
5. Host and guest VM.
6. Local system and network.
7. Project source, and everything built from it.

## Trust assumptions

These are assumed, not established. Each is a risk.

- CPU, MMU and IOMMU behave as documented, apart from known errata.
- Platform firmware is not malicious. Fyrkat cannot remove it from the TCB on commodity
  hardware.
- The Rust compiler and core library are correct.
- Whichever kernel is used is correct for the shipped configuration. seL4's proofs do not
  cover every configuration Fyrkat may need, and a custom kernel would have no proofs at
  first.
- Cryptographic primitives are sound.

## Required properties

Every property below needs a negative test before it may be claimed.

| Threat | Required property | How it will be shown |
|---|---|---|
| Application reads another's memory | Address space isolation | Negative tests that attempt the access |
| Application acts without authority | No ambient authority | Tests that a component without a capability is refused |
| Authority outlives its grant | Revocation that takes effect | Use-after-revoke tests |
| Driver crash | Fault containment and restart | Fault injection |
| Driver or device reaches other memory by DMA | IOMMU enforcement | DMA outside the mapped region must fault |
| Memory reused while a device can reach it | Correct teardown ordering | Reuse tests after device teardown |
| Resource exhaustion by a component | Accounted and bounded resources | Exhaustion tests against unrelated components |
| Guest escapes its VM | Virtualization isolation | Malicious guest tests |
| Malformed input to a service | Robust parsing | Fuzzing |
| Offline access to storage | Encryption at rest | Design review, then testing |
| Tampered boot chain | Verified and measured boot | Later work, on hardware |
| Tampered update | Signed, reversible updates | Later work |

## Out of scope for now

These are not dismissed. They are not goals until an ADR says otherwise.

- **Hardware implants and lab-grade physical attacks,** such as decapping or fault injection.
- **Malicious firmware.** Fyrkat can detect some tampering through measured boot, and cannot
  prevent it.
- **Rowhammer-class attacks.** seL4 explicitly offers no protection, and Fyrkat has no plan
  yet.
- **Availability against a physically present attacker.**

## Open: side channels

Speculative execution and timing channels are unresolved, and are the largest gap here.

- seL4's confidentiality proofs make no guarantee about covert timing channels. Its
  documentation says no release configuration provides timing or micro-architectural
  channel guarantees. [Documented]
- Mitigations cost performance, and must be included in any IPC measurement. Published
  figures are often reported without them.
- A policy must exist before Fyrkat runs mutually distrusting code on shared cores.

## Project and supply chain threats

| Threat | Control | Status |
|---|---|---|
| Malicious dependency | `cargo-deny`, reviewed additions, lockfile | Being set up in M0 |
| Compromised CI action | Actions pinned by commit SHA, least-privilege permissions | Being set up in M0 |
| Toolchain drift | Pinned toolchain | Set up |
| Unreviewed change reaching `main` | Branch protection, PR-only | Set up and read back through the API on 2026-11-07. Direct-push rejection is not yet demonstrated. A required check blocked a failing PR |
| Forged commits | Signed commits | Set up locally. GitHub does not require signatures, and squash merges are re-signed by GitHub |
| Compromised release | Signing and reproducible builds | Later work |
| **Single maintainer** | None yet. One compromised account defeats the controls above | **Open risk** |
| **Prompt injection through researched content** | Downloaded content is data, never instructions; agents have limited authority | Policy only |
| **Flawed AI-generated code** | No exemption from review, tests or static analysis | Policy only |

Review by another AI session is not independent human review. Until the project has a second
maintainer, security-sensitive changes have no independent human reviewer, and that gap must
be stated rather than hidden.
