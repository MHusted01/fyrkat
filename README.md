# Fyrkat

Fyrkat is a research-stage project to build a secure, reliable operating system in Rust.

## Status

**There is no kernel and no operating system yet.** There is nothing to boot, install or
run. The repository holds design records, research, and the build and verification
infrastructure that future code will use.

What exists today:

- Architecture decision records, mostly Proposed or Provisional. Whether to build on seL4 or
  write a Rust kernel is undecided: [ADR 0004](docs/adr/0004-kernel-foundation.md).
- Research notes and disposable feasibility spikes under `spikes/`.
- A task runner (`cargo xtask`) and a tiny UEFI test application that checks the toolchain
  and firmware pipeline under QEMU. It is not a kernel.

Nothing is supported ([supported platforms](docs/supported-platforms.md)).

## Documents

- [Architecture overview](docs/architecture/overview.md) and [threat model](docs/architecture/threat-model.md)
- [Roadmap](docs/roadmap.md)
- [Architecture decision records](docs/adr/README.md)
- [Development setup](docs/development.md)
- [Engineering standards](docs/standards/engineering.md)
- [Contributing](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for AI agents
- [Security policy](SECURITY.md)

## Try the checks

```sh
cargo xtask tools && cargo xtask check && cargo xtask boot
```

See [docs/development.md](docs/development.md) for prerequisites.

## Licence

Dual licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option.
Unless you state otherwise, any contribution you submit is licensed the same way, without
additional terms.
