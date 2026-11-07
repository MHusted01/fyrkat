# What "AI-native" means for Fyrkat's architecture

- **Status:** Draft proposal for the owner. Nothing here is decided. It adds no criterion to the
  [spike plan](sel4-spike-plan.md) and no requirement to any ADR.
- **Purpose:** turn the phrase into measurable architectural requirements, and say which ones S1
  already measures and which belong later.
- **Scope rule:** S1 stays a kernel-foundation spike. This document proposes **no new S1
  experiment**.

## What the repository says today

[Documented] The term "AI-native" appears in no ADR, architecture document, roadmap entry or
standard. The nearest statements are:

- Roadmap, "Later work": "Local AI inference, and permission-controlled agents." Unscheduled.
- [Architecture overview](../architecture/overview.md): "How capabilities surface to users and
  applications as understandable permissions" is open. "What is the GPU strategy" is open. "What is
  the capability revocation model" is open. "Whether revoking a single grant needs user-level
  indirection" is open.
- Roadmap research items R1 (GPU strategy and driver-VM cost), R3 (heterogeneous cores) and R5
  (speculative side channels, "running mutually distrusting code").
- [Threat model](../architecture/threat-model.md): a compromised contributor or agent is an
  adversary, and "Authority outlives its grant" requires use-after-revoke tests.

So the term is the owner's stated goal and has no definition in the project yet.

## A proposed working definition

[Proposal, for ratification] **An agent** is software whose actions are chosen at run time by a
model and cannot be fully predicted from its code. Fyrkat is AI-native if it treats an agent as an
**untrusted principal** that:

1. is confined to the capabilities it holds, even when it is compromised or misbehaves;
2. can delegate only a subset of its authority, and cannot amplify it;
3. can have any grant revoked completely and promptly;
4. reaches large shared data (model weights) and accelerators only through grants that stay
   confined and revocable; and
5. is bounded and accounted, so that one agent cannot starve another.

This follows from ADR 0001's requirements 1 and 2 and from the threat model. It adds the delegation
and sharing cases that agents make common. It does not require the OS to contain a model.

## Proposed requirements

Each is a measurable property with a negative test. The "S1" column says whether an existing S1
experiment already measures it. [Inferred: the mapping is mine and the owner should check it.]

| ID | Requirement | Measurable form | In S1? |
|---|---|---|---|
| AR1 | **Agent confinement.** A compromised agent cannot touch anything outside its capabilities | 1,000 injected faults (wild writes, illegal capability use, kill) leave unrelated components' memory checksums unchanged, with no kernel fault | **Yes.** P1, P2, P4 through B3 and B4 |
| AR2 | **Delegation by attenuation.** An agent can pass on strictly fewer rights, and the receiver cannot amplify | Mint, copy and mutate chains to depth 1,000. Every amplification and forged-badge attempt is refused with no effect | **Yes.** P2 through B2 and B4 |
| AR3 | **Complete, prompt revocation, including one grant among many.** After revoke returns nothing derived is usable, and revoking one grant leaves its siblings working | Use after revoke observed 0 times. Interrupt delay at most 1 ms in the 100,000-capability tree. Revoking 1 of 1,000 sibling grants leaves 999 usable | **Yes.** P3 through B2. The sibling case is B2's own "revoke one grant among many" Conditional. The results file records it, and the plan needs no change |
| AR4 | **DMA and accelerator confinement.** A device reaches only memory granted to its holder, and revocation stops device access before the memory is reused | The four P5 tests pass | **Yes**, as the precondition for any accelerator. A5-arm |
| AR5 | **Revocable shared memory.** N agents map one read-only model region without N copies, and revoking removes it from all of them | Physical memory for N mappings is one copy plus page tables. A write attempt faults. After revoke, access faults in N of N mappers, and reused memory shows no old data | **Deferred** to M3. Partly seen in B1, B3 and C2's file-backed workload F2 |
| AR6 | **Bounded resources.** An agent's memory, capability slots and CPU use are budgeted and accounted | An agent that allocates to its budget leaves unrelated components' latency and memory unchanged | **Deferred.** Memory is visible through untyped accounting in B1. CPU budgets need MCS, which is U on AArch64 |
| AR7 | **Auditable delegation.** Every grant, delegation and revocation is visible to a trusted audit service | 100% of grant events appear in the log, with no path that bypasses it | **Deferred.** User-level design, needs the broker design first |
| AR8 | **Policy for mutually distrusting agents on shared cores.** Timing and speculative channels have a stated policy | A written policy and a measured mitigation cost (roadmap R5) | **Deferred.** The plan marks timing channels out of scope |
| AR9 | **Isolation does not make inference impractical.** Tool-call IPC and shared-weight access cost little against the model's own work | A workload-based measurement, such as per-token overhead against a monolithic baseline | **Deferred.** Needs a workload and an accelerator strategy (R1, R3) |

## What S1 should do with this

1. **Nothing new to run.** AR1 to AR4 are already measured by experiments the plan defines.
2. **Report through the lens.** When Stage D weighs the results, it can read B2 as AR3 and A5-arm as
   AR4. That needs no plan change.
3. **Record one extra number in B2's results file:** whether revoking a single grant among many
   leaves its siblings usable. The plan already requires B2 to list gaps that need user-level
   indirection, so this fits the existing text.
4. **Defer AR5 to AR9.** They need designs that S1 does not produce. AR5 is cheap and is the first
   to add, once M3 has processes and a pager.

## Hypothesis worth testing later

[Hypothesis, not evidence] Agent delegation produces grants that cut across seL4's derivation tree.
"Revoke everything agent X holds" spans many subtrees, and the plan already expects user-level
indirection to be needed for single-grant revocation. A small user-level broker that issues every
agent grant as an indirection object could give per-agent and per-grant revocation. It would also
become a trusted component for P2 and P3. A falsifiable test: revoke all grants of one agent across
1,000 subtrees in time proportional to that agent's grants, with no use after revoke, and an A2 row
for the broker. This belongs after S1 and needs the owner's authorization.

## Open questions for the owner

- Ratify, change or reject the working definition.
- Should AR1 to AR4 become a named lens in ADR 0004, or stay as reading guidance for Stage D?
- Is AR5 wanted as an explicit M3 exit criterion?
