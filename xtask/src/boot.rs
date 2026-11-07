//! `cargo xtask boot`: build boot-smoke and run it under QEMU until the marker appears.

use crate::error::{Result, XtaskError};
use crate::process::Cmd;
use crate::qemu::{Accel, Arch, find_firmware, marker_seen, qemu_args, resolve_accel};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::time::{Duration, Instant};

const APPLE_SILICON_HOST: bool = cfg!(all(target_os = "macos", target_arch = "aarch64"));
const POLL_INTERVAL: Duration = Duration::from_millis(20);
const TAIL_BYTES: usize = 400;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BootOptions {
    pub archs: Vec<Arch>,
    pub accel: Accel,
    pub timeout: Duration,
}

impl Default for BootOptions {
    fn default() -> Self {
        Self {
            archs: Arch::ALL.to_vec(),
            accel: Accel::Tcg,
            timeout: Duration::from_secs(90),
        }
    }
}

/// Boot every selected architecture. Stops at the first failure.
pub fn run(root: &Path, options: &BootOptions) -> Result<()> {
    for &arch in &options.archs {
        let (accel, note) = resolve_accel(arch, options.accel, APPLE_SILICON_HOST)?;
        if let Some(note) = note {
            println!("note: {note}");
        }
        let started = Instant::now();
        boot_one(root, arch, accel, options.timeout)?;
        println!(
            "PASS boot {} ({}) in {:.1}s",
            arch.name(),
            accel.name(),
            started.elapsed().as_secs_f64()
        );
    }
    Ok(())
}

fn boot_one(root: &Path, arch: Arch, accel: Accel, timeout: Duration) -> Result<()> {
    println!("==> boot-smoke {} ({})", arch.name(), accel.name());
    let efi = build_efi(root, arch)?;
    let esp = stage_esp(root, arch, &efi)?;
    let firmware = locate_firmware(arch)?;
    let args = qemu_args(arch, accel, &firmware, &esp);
    run_qemu(arch.qemu_binary(), &args, timeout)
}

fn build_efi(root: &Path, arch: Arch) -> Result<PathBuf> {
    Cmd::new("cargo")
        .args([
            "build",
            "--package",
            "boot-smoke",
            "--release",
            "--target",
            arch.uefi_target(),
        ])
        .dir(root)
        .run()?;
    let efi = root
        .join("target")
        .join(arch.uefi_target())
        .join("release")
        .join("boot-smoke.efi");
    if efi.is_file() {
        Ok(efi)
    } else {
        Err(XtaskError::new(format!(
            "build produced no {}",
            efi.display()
        )))
    }
}

/// Lay out a FAT-less ESP directory; QEMU presents it as a FAT disk.
fn stage_esp(root: &Path, arch: Arch, efi: &Path) -> Result<PathBuf> {
    let esp = root
        .join("target")
        .join("boot-smoke")
        .join(format!("esp-{}", arch.name()));
    let boot_dir = esp.join("EFI").join("BOOT");
    if esp.exists() {
        std::fs::remove_dir_all(&esp).map_err(|e| XtaskError::io("clearing old ESP", &e))?;
    }
    std::fs::create_dir_all(&boot_dir).map_err(|e| XtaskError::io("creating ESP", &e))?;
    std::fs::copy(efi, boot_dir.join(arch.efi_file()))
        .map_err(|e| XtaskError::io("copying EFI image into ESP", &e))?;
    Ok(esp)
}

fn locate_firmware(arch: Arch) -> Result<PathBuf> {
    if let Some(custom) = std::env::var_os(arch.firmware_env()) {
        let path = PathBuf::from(custom);
        return if path.is_file() {
            Ok(path)
        } else {
            Err(XtaskError::new(format!(
                "{} points to a missing file",
                arch.firmware_env()
            )))
        };
    }
    find_firmware(arch.firmware_candidates(), Path::is_file).ok_or_else(|| {
        XtaskError::new(format!(
            "no {} UEFI firmware found. Install QEMU's EDK2 firmware (see docs/development.md) \
             or set {}",
            arch.name(),
            arch.firmware_env()
        ))
    })
}

enum Outcome {
    Marker,
    EndOfOutput,
    TimedOut,
}

fn spawn_reader(mut source: impl Read + Send + 'static) -> Receiver<Vec<u8>> {
    let (sender, receiver) = mpsc::channel();
    std::thread::spawn(move || {
        let mut buffer = [0u8; 4096];
        // A read error ends the stream. The caller then reports a missing marker.
        while let Ok(count) = source.read(&mut buffer) {
            if count == 0 || sender.send(buffer[..count].to_vec()).is_err() {
                break;
            }
        }
    });
    receiver
}

fn read_until_marker(chunks: &Receiver<Vec<u8>>, deadline: Instant, log: &mut Vec<u8>) -> Outcome {
    loop {
        if marker_seen(log) {
            return Outcome::Marker;
        }
        let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
            return Outcome::TimedOut;
        };
        match chunks.recv_timeout(remaining) {
            Ok(chunk) => log.extend(chunk),
            Err(RecvTimeoutError::Timeout) => return Outcome::TimedOut,
            Err(RecvTimeoutError::Disconnected) => return Outcome::EndOfOutput,
        }
    }
}

fn tail(log: &[u8]) -> String {
    let start = log.len().saturating_sub(TAIL_BYTES);
    String::from_utf8_lossy(log.get(start..).unwrap_or_default()).into_owned()
}

fn kill(child: &mut Child) {
    // The child may already have exited. Both outcomes leave nothing to clean up.
    if child.kill().is_ok() {
        drop(child.wait());
    }
}

fn wait_for_exit(child: &mut Child, deadline: Instant) -> Result<()> {
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return Ok(()),
            Ok(Some(status)) => {
                return Err(XtaskError::new(format!(
                    "marker seen but QEMU exited with {status}"
                )));
            }
            Ok(None) if Instant::now() < deadline => std::thread::sleep(POLL_INTERVAL),
            Ok(None) => {
                kill(child);
                return Err(XtaskError::new(
                    "marker seen but the guest did not shut down in time",
                ));
            }
            Err(e) => return Err(XtaskError::io("waiting for QEMU", &e)),
        }
    }
}

fn run_qemu(binary: &str, args: &[String], timeout: Duration) -> Result<()> {
    let mut child = Command::new(binary)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|e| XtaskError::io(format!("starting {binary} (is QEMU installed?)"), &e))?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| XtaskError::new("QEMU stdout unavailable"))?;
    let chunks = spawn_reader(stdout);
    let deadline = Instant::now() + timeout;
    let mut log = Vec::new();
    match read_until_marker(&chunks, deadline, &mut log) {
        Outcome::Marker => wait_for_exit(&mut child, deadline),
        Outcome::TimedOut => {
            kill(&mut child);
            Err(XtaskError::new(format!(
                "no marker within {}s. Output tail:\n{}",
                timeout.as_secs(),
                tail(&log)
            )))
        }
        Outcome::EndOfOutput => {
            let status = child
                .wait()
                .map_err(|e| XtaskError::io("waiting for QEMU", &e))?;
            Err(XtaskError::new(format!(
                "QEMU exited ({status}) without the marker. Output tail:\n{}",
                tail(&log)
            )))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn feed(chunks: &[&[u8]]) -> Receiver<Vec<u8>> {
        let (sender, receiver) = mpsc::channel();
        for chunk in chunks {
            sender.send(chunk.to_vec()).unwrap();
        }
        receiver
    }

    #[test]
    fn marker_split_across_chunks_is_found() {
        let receiver = feed(&[b"boot FYRKAT-BOOT", b"-SMOKE: ok\r\n"]);
        let mut log = Vec::new();
        let deadline = Instant::now() + Duration::from_secs(5);
        assert!(matches!(
            read_until_marker(&receiver, deadline, &mut log),
            Outcome::Marker
        ));
    }

    #[test]
    fn closed_stream_without_marker_is_end_of_output() {
        let receiver = feed(&[b"nothing here"]);
        let mut log = Vec::new();
        let deadline = Instant::now() + Duration::from_secs(5);
        assert!(matches!(
            read_until_marker(&receiver, deadline, &mut log),
            Outcome::EndOfOutput
        ));
    }

    #[test]
    fn silent_open_stream_times_out() {
        let (_sender, receiver) = mpsc::channel::<Vec<u8>>();
        let mut log = Vec::new();
        let deadline = Instant::now() + Duration::from_millis(50);
        assert!(matches!(
            read_until_marker(&receiver, deadline, &mut log),
            Outcome::TimedOut
        ));
    }

    #[test]
    fn tail_keeps_only_the_end() {
        let log = vec![b'x'; TAIL_BYTES * 2];
        assert_eq!(tail(&log).len(), TAIL_BYTES);
        assert_eq!(tail(b"short"), "short");
    }

    #[test]
    fn missing_qemu_binary_is_a_clear_error() {
        let error = run_qemu("fyrkat-no-such-qemu", &[], Duration::from_secs(1)).unwrap_err();
        assert!(error.to_string().contains("is QEMU installed"), "{error}");
    }

    #[test]
    fn a_process_that_prints_the_marker_and_exits_passes() {
        let args = ["-c".to_owned(), "echo FYRKAT-BOOT-SMOKE: ok".to_owned()];
        assert!(run_qemu("sh", &args, Duration::from_secs(5)).is_ok());
    }

    #[test]
    fn a_process_that_never_prints_the_marker_fails() {
        let args = ["-c".to_owned(), "echo nope".to_owned()];
        let error = run_qemu("sh", &args, Duration::from_secs(5)).unwrap_err();
        assert!(error.to_string().contains("without the marker"), "{error}");
    }

    #[test]
    fn a_hung_process_is_killed_at_the_timeout() {
        let args = ["-c".to_owned(), "exec sleep 30".to_owned()];
        let error = run_qemu("sh", &args, Duration::from_millis(200)).unwrap_err();
        assert!(error.to_string().contains("no marker within"), "{error}");
    }
}
