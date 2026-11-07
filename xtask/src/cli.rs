//! Command-line parsing for `cargo xtask`.

use crate::boot::BootOptions;
use crate::error::{Result, XtaskError};
use crate::qemu::{Accel, Arch};
use std::time::Duration;

pub const USAGE: &str = "\
Usage: cargo xtask <command>

Commands:
  tools                      Install pinned tools into .tools/ (cargo-nextest, cargo-deny)
  check                      Run every verification step; CI runs this too
  boot [options]             Build boot-smoke and boot it under QEMU
  help                       Show this message

Options for boot:
  --arch <aarch64|x86_64|all>   Guest architecture (default: all)
  --accel <tcg|hvf>             Accelerator (default: tcg; hvf is AArch64 on Apple Silicon only)
  --timeout <seconds>           Per-guest timeout (default: 90)
";

#[derive(Debug, PartialEq, Eq)]
pub enum Command {
    Tools,
    Check,
    Boot(BootOptions),
    Help,
}

pub fn parse(args: &[String]) -> Result<Command> {
    let mut iter = args.iter().map(String::as_str);
    match iter.next() {
        None | Some("help" | "--help" | "-h") => Ok(Command::Help),
        Some("tools") => no_extra(iter, Command::Tools),
        Some("check") => no_extra(iter, Command::Check),
        Some("boot") => parse_boot(iter).map(Command::Boot),
        Some(other) => Err(XtaskError::new(format!(
            "unknown command `{other}`\n\n{USAGE}"
        ))),
    }
}

fn no_extra<'a>(mut rest: impl Iterator<Item = &'a str>, command: Command) -> Result<Command> {
    match rest.next() {
        None => Ok(command),
        Some(extra) => Err(XtaskError::new(format!("unexpected argument `{extra}`"))),
    }
}

fn value<'a>(rest: &mut impl Iterator<Item = &'a str>, flag: &str) -> Result<&'a str> {
    rest.next()
        .ok_or_else(|| XtaskError::new(format!("{flag} needs a value")))
}

fn parse_boot<'a>(mut rest: impl Iterator<Item = &'a str>) -> Result<BootOptions> {
    let mut options = BootOptions::default();
    while let Some(flag) = rest.next() {
        match flag {
            "--arch" => options.archs = parse_arch(value(&mut rest, flag)?)?,
            "--accel" => options.accel = parse_accel(value(&mut rest, flag)?)?,
            "--timeout" => options.timeout = parse_timeout(value(&mut rest, flag)?)?,
            other => return Err(XtaskError::new(format!("unknown boot option `{other}`"))),
        }
    }
    Ok(options)
}

fn parse_arch(text: &str) -> Result<Vec<Arch>> {
    match text {
        "aarch64" => Ok(vec![Arch::Aarch64]),
        "x86_64" | "x86-64" => Ok(vec![Arch::X86_64]),
        "all" => Ok(Arch::ALL.to_vec()),
        other => Err(XtaskError::new(format!("unknown architecture `{other}`"))),
    }
}

fn parse_accel(text: &str) -> Result<Accel> {
    match text {
        "tcg" => Ok(Accel::Tcg),
        "hvf" => Ok(Accel::Hvf),
        other => Err(XtaskError::new(format!(
            "unknown accelerator `{other}` (use tcg or hvf)"
        ))),
    }
}

fn parse_timeout(text: &str) -> Result<Duration> {
    match text.parse::<u64>() {
        Ok(seconds) if seconds > 0 => Ok(Duration::from_secs(seconds)),
        _ => Err(XtaskError::new(format!(
            "invalid timeout `{text}`: use a positive whole number"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_str(line: &str) -> Result<Command> {
        let args: Vec<String> = line.split_whitespace().map(str::to_owned).collect();
        parse(&args)
    }

    #[test]
    fn simple_commands() {
        assert_eq!(parse_str("").unwrap(), Command::Help);
        assert_eq!(parse_str("check").unwrap(), Command::Check);
        assert_eq!(parse_str("tools").unwrap(), Command::Tools);
    }

    #[test]
    fn boot_defaults_to_both_architectures_under_tcg() {
        let Command::Boot(options) = parse_str("boot").unwrap() else {
            unreachable!()
        };
        assert_eq!(options.archs, Arch::ALL.to_vec());
        assert_eq!(options.accel, Accel::Tcg);
    }

    #[test]
    fn boot_options_are_parsed() {
        let line = "boot --arch aarch64 --accel hvf --timeout 30";
        let Command::Boot(options) = parse_str(line).unwrap() else {
            unreachable!()
        };
        assert_eq!(options.archs, vec![Arch::Aarch64]);
        assert_eq!(options.accel, Accel::Hvf);
        assert_eq!(options.timeout, Duration::from_secs(30));
    }

    #[test]
    fn bad_input_is_rejected_with_a_message() {
        for line in [
            "nope",
            "check extra",
            "boot --arch",
            "boot --arch arm",
            "boot --accel kvm",
            "boot --timeout 0",
            "boot --timeout x",
            "boot --frobnicate",
        ] {
            assert!(parse_str(line).is_err(), "{line} should fail");
        }
    }
}
