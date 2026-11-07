//! Pure helpers for running boot-smoke under QEMU: architectures, firmware, arguments.

use crate::error::{Result, XtaskError};
use std::path::{Path, PathBuf};

/// The line boot-smoke prints. Kept in sync with `tests/boot-smoke/src/main.rs` by a test.
pub const MARKER: &str = "FYRKAT-BOOT-SMOKE: ok";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Arch {
    Aarch64,
    X86_64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Accel {
    Tcg,
    Hvf,
}

impl Accel {
    pub fn name(self) -> &'static str {
        match self {
            Self::Tcg => "tcg",
            Self::Hvf => "hvf",
        }
    }
}

impl Arch {
    pub const ALL: [Self; 2] = [Self::Aarch64, Self::X86_64];

    pub fn name(self) -> &'static str {
        match self {
            Self::Aarch64 => "aarch64",
            Self::X86_64 => "x86_64",
        }
    }

    pub fn uefi_target(self) -> &'static str {
        match self {
            Self::Aarch64 => "aarch64-unknown-uefi",
            Self::X86_64 => "x86_64-unknown-uefi",
        }
    }

    /// The path firmware looks for on a removable boot medium.
    pub fn efi_file(self) -> &'static str {
        match self {
            Self::Aarch64 => "BOOTAA64.EFI",
            Self::X86_64 => "BOOTX64.EFI",
        }
    }

    pub fn qemu_binary(self) -> &'static str {
        match self {
            Self::Aarch64 => "qemu-system-aarch64",
            Self::X86_64 => "qemu-system-x86_64",
        }
    }

    /// Environment variable that overrides firmware discovery.
    pub fn firmware_env(self) -> &'static str {
        match self {
            Self::Aarch64 => "FYRKAT_FIRMWARE_AARCH64",
            Self::X86_64 => "FYRKAT_FIRMWARE_X86_64",
        }
    }

    /// Known firmware locations: Homebrew on macOS (Apple Silicon and Intel), then Debian
    /// and Ubuntu packages (`qemu-efi-aarch64`, `ovmf`), then Fedora-style paths.
    pub fn firmware_candidates(self) -> &'static [&'static str] {
        match self {
            Self::Aarch64 => &[
                "/opt/homebrew/share/qemu/edk2-aarch64-code.fd",
                "/usr/local/share/qemu/edk2-aarch64-code.fd",
                "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd",
                "/usr/share/AAVMF/AAVMF_CODE.fd",
                "/usr/share/edk2/aarch64/QEMU_EFI.fd",
            ],
            Self::X86_64 => &[
                "/opt/homebrew/share/qemu/edk2-x86_64-code.fd",
                "/usr/local/share/qemu/edk2-x86_64-code.fd",
                "/usr/share/OVMF/OVMF_CODE_4M.fd",
                "/usr/share/OVMF/OVMF_CODE.fd",
                "/usr/share/edk2/ovmf/OVMF_CODE.fd",
            ],
        }
    }
}

/// Choose the accelerator. HVF is available only for `AArch64` guests on Apple Silicon.
///
/// Returns the accelerator to use and an optional note for the user.
pub fn resolve_accel(
    arch: Arch,
    requested: Accel,
    apple_silicon_host: bool,
) -> Result<(Accel, Option<String>)> {
    match (requested, arch) {
        (Accel::Tcg, _) => Ok((Accel::Tcg, None)),
        (Accel::Hvf, Arch::Aarch64) if apple_silicon_host => Ok((Accel::Hvf, None)),
        (Accel::Hvf, Arch::Aarch64) => Err(XtaskError::new(
            "--accel hvf needs an AArch64 macOS host; use --accel tcg",
        )),
        (Accel::Hvf, Arch::X86_64) => Ok((
            Accel::Tcg,
            Some("x86_64 guest cannot use hvf on this project's hosts; using tcg".to_owned()),
        )),
    }
}

/// The first candidate that `exists`.
pub fn find_firmware(candidates: &[&str], exists: impl Fn(&Path) -> bool) -> Option<PathBuf> {
    candidates.iter().map(PathBuf::from).find(|p| exists(p))
}

/// Whether the serial output contains the success marker.
pub fn marker_seen(output: &[u8]) -> bool {
    String::from_utf8_lossy(output).contains(MARKER)
}

/// QEMU arguments to boot `esp` (a directory holding `EFI/BOOT/...`) with `firmware`.
pub fn qemu_args(arch: Arch, accel: Accel, firmware: &Path, esp: &Path) -> Vec<String> {
    let firmware = firmware.display();
    let disk = format!("format=raw,file=fat:rw:{}", esp.display());
    let mut args: Vec<String> = match arch {
        Arch::Aarch64 => {
            let cpu = if accel == Accel::Hvf {
                "host"
            } else {
                "cortex-a76"
            };
            ["-machine", "virt", "-accel", accel.name(), "-cpu", cpu]
                .map(str::to_owned)
                .into()
        }
        Arch::X86_64 => ["-machine", "q35", "-accel", accel.name()]
            .map(str::to_owned)
            .into(),
    };
    args.extend(
        [
            "-m",
            "512M",
            "-nographic",
            "-monitor",
            "none",
            "-serial",
            "stdio",
            "-no-reboot",
        ]
        .map(str::to_owned),
    );
    match arch {
        Arch::Aarch64 => args.extend(["-bios".to_owned(), firmware.to_string()]),
        Arch::X86_64 => args.extend([
            "-drive".to_owned(),
            format!("if=pflash,format=raw,readonly=on,file={firmware}"),
        ]),
    }
    args.extend(["-drive".to_owned(), disk]);
    // Without menu=on,splash-time=0, EDK2 waits about 5 seconds before booting.
    args.extend(["-boot".to_owned(), "menu=on,splash-time=0".to_owned()]);
    args
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn marker_matches_boot_smoke_source() {
        let source = include_str!("../../tests/boot-smoke/src/main.rs");
        assert!(
            source.contains(MARKER),
            "boot-smoke does not print {MARKER}"
        );
    }

    #[test]
    fn marker_is_found_amid_firmware_noise() {
        assert!(marker_seen(
            b"\x1b[2JBdsDxe...\r\nFYRKAT-BOOT-SMOKE: ok\r\n"
        ));
        assert!(!marker_seen(b"FYRKAT-BOOT-SMOKE: fail"));
    }

    #[test]
    fn hvf_is_limited_to_aarch64_on_apple_silicon() {
        assert_eq!(
            resolve_accel(Arch::Aarch64, Accel::Hvf, true).unwrap().0,
            Accel::Hvf
        );
        assert!(resolve_accel(Arch::Aarch64, Accel::Hvf, false).is_err());
        let (accel, note) = resolve_accel(Arch::X86_64, Accel::Hvf, true).unwrap();
        assert_eq!(accel, Accel::Tcg);
        assert!(note.is_some());
        assert_eq!(
            resolve_accel(Arch::X86_64, Accel::Tcg, false).unwrap(),
            (Accel::Tcg, None)
        );
    }

    #[test]
    fn first_existing_firmware_wins() {
        let found = find_firmware(&["/a", "/b", "/c"], |p| p != Path::new("/a"));
        assert_eq!(found, Some(PathBuf::from("/b")));
        assert_eq!(find_firmware(&["/a"], |_| false), None);
    }

    #[test]
    fn x86_64_uses_pflash_and_no_boot_delay() {
        let args = qemu_args(
            Arch::X86_64,
            Accel::Tcg,
            Path::new("/fw"),
            Path::new("/esp"),
        );
        let joined = args.join(" ");
        assert!(
            joined.contains("if=pflash,format=raw,readonly=on,file=/fw"),
            "{joined}"
        );
        assert!(joined.contains("-boot menu=on,splash-time=0"), "{joined}");
        assert!(joined.contains("-accel tcg"), "{joined}");
        assert!(joined.contains("file=fat:rw:/esp"), "{joined}");
    }

    #[test]
    fn aarch64_uses_bios_and_host_cpu_under_hvf() {
        let args = qemu_args(
            Arch::Aarch64,
            Accel::Hvf,
            Path::new("/fw"),
            Path::new("/esp"),
        );
        let joined = args.join(" ");
        assert!(joined.contains("-bios /fw"), "{joined}");
        assert!(joined.contains("-accel hvf -cpu host"), "{joined}");
    }

    #[test]
    fn every_arch_has_firmware_candidates_for_both_platforms() {
        for arch in Arch::ALL {
            let paths = arch.firmware_candidates();
            assert!(paths.iter().any(|p| p.contains("homebrew")), "{arch:?}");
            assert!(
                paths.iter().any(|p| p.starts_with("/usr/share/")),
                "{arch:?}"
            );
        }
    }
}
