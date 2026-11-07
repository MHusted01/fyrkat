//! Pinned developer tools, installed into the gitignored `.tools/` directory.

use crate::error::{Result, XtaskError};
use crate::process::Cmd;
use std::ffi::OsString;
use std::path::{Path, PathBuf};

/// A Cargo-installed tool and the exact version this repository is verified with.
#[derive(Debug)]
pub struct Tool {
    pub crate_name: &'static str,
    pub version: &'static str,
    pub binary: &'static str,
    /// Arguments that make the binary print its version.
    pub version_args: &'static [&'static str],
}

/// The only place tool versions are pinned. Changing a version is a reviewed change.
pub const TOOLS: &[Tool] = &[
    Tool {
        crate_name: "cargo-nextest",
        version: "0.9.150",
        binary: "cargo-nextest",
        version_args: &["nextest", "--version"],
    },
    Tool {
        crate_name: "cargo-deny",
        version: "0.20.2",
        binary: "cargo-deny",
        version_args: &["--version"],
    },
];

pub fn bin_dir(root: &Path) -> PathBuf {
    root.join(".tools").join("bin")
}

/// `PATH` with `.tools/bin` first, so that `cargo nextest` and `cargo deny` resolve there.
pub fn path_with_tools(root: &Path) -> Result<OsString> {
    let existing = std::env::var_os("PATH").unwrap_or_default();
    let entries = std::iter::once(bin_dir(root)).chain(std::env::split_paths(&existing));
    std::env::join_paths(entries).map_err(|e| XtaskError::new(format!("cannot build PATH: {e}")))
}

/// Whether tool output names exactly the pinned version as one of its words.
pub fn version_matches(output: &str, expected: &str) -> bool {
    output.split_whitespace().any(|word| word == expected)
}

/// Install every pinned tool. `cargo install` skips a tool that is already current.
pub fn install(root: &Path) -> Result<()> {
    let prefix = root.join(".tools");
    for tool in TOOLS {
        println!("==> installing {} {}", tool.crate_name, tool.version);
        Cmd::new("cargo")
            .args(["install", "--locked", "--root"])
            .args([prefix.to_string_lossy().into_owned()])
            .args(["--version", tool.version, tool.crate_name])
            .dir(root)
            .run()?;
    }
    Ok(())
}

/// Confirm a tool is present in `.tools/bin` at the pinned version.
pub fn verify(root: &Path, tool: &Tool) -> Result<()> {
    let binary = bin_dir(root).join(tool.binary);
    if !binary.is_file() {
        return Err(XtaskError::new(format!(
            "{} is not installed in .tools/bin. Run `cargo xtask tools`",
            tool.crate_name
        )));
    }
    let program = binary.to_string_lossy().into_owned();
    let output = Cmd::new(program)
        .args(tool.version_args.iter().copied())
        .capture()?;
    if version_matches(&output, tool.version) {
        Ok(())
    } else {
        Err(XtaskError::new(format!(
            "{} is not version {}. Run `cargo xtask tools` (found: {})",
            tool.crate_name,
            tool.version,
            output.trim()
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_must_match_a_whole_word() {
        assert!(version_matches("cargo-deny 0.20.2", "0.20.2"));
        assert!(!version_matches("cargo-deny 0.20.21", "0.20.2"));
        assert!(!version_matches("", "0.20.2"));
    }

    #[test]
    fn pins_are_exact_versions() {
        for tool in TOOLS {
            assert!(
                tool.version.split('.').count() == 3,
                "{} is not x.y.z",
                tool.crate_name
            );
            assert!(tool.version.chars().all(|c| c.is_ascii_digit() || c == '.'));
        }
    }

    #[test]
    fn path_puts_tools_first() {
        let root = Path::new("/repo");
        let path = path_with_tools(root).unwrap();
        let first = std::env::split_paths(&path).next().unwrap();
        assert_eq!(first, Path::new("/repo/.tools/bin"));
    }

    #[test]
    fn missing_tool_reports_how_to_install() {
        let error = verify(Path::new("/nonexistent-root"), &TOOLS[0]).unwrap_err();
        assert!(error.to_string().contains("cargo xtask tools"), "{error}");
    }
}
