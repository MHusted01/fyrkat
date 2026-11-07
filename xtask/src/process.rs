//! Running external commands with clear failure messages.

use crate::error::{Result, XtaskError};
use std::ffi::OsString;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

/// A command to run from the repository root.
#[derive(Debug, Clone)]
pub struct Cmd {
    program: String,
    args: Vec<String>,
    envs: Vec<(String, OsString)>,
    dir: Option<PathBuf>,
}

impl Cmd {
    pub fn new(program: impl Into<String>) -> Self {
        Self {
            program: program.into(),
            args: Vec::new(),
            envs: Vec::new(),
            dir: None,
        }
    }

    #[must_use]
    pub fn args<I, S>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.args.extend(args.into_iter().map(Into::into));
        self
    }

    #[must_use]
    pub fn env(mut self, key: &str, value: impl Into<OsString>) -> Self {
        self.envs.push((key.to_owned(), value.into()));
        self
    }

    #[must_use]
    pub fn dir(mut self, dir: &Path) -> Self {
        self.dir = Some(dir.to_path_buf());
        self
    }

    /// The command as a shell-like string, for messages.
    pub fn display(&self) -> String {
        let mut parts = vec![self.program.clone()];
        parts.extend(self.args.iter().cloned());
        parts.join(" ")
    }

    fn build(&self) -> Command {
        let mut command = Command::new(&self.program);
        command.args(&self.args);
        for (key, value) in &self.envs {
            command.env(key, value);
        }
        if let Some(dir) = &self.dir {
            command.current_dir(dir);
        }
        command
    }

    fn spawn_error(&self, error: &std::io::Error) -> XtaskError {
        if error.kind() == ErrorKind::NotFound {
            XtaskError::new(format!(
                "`{}` was not found. Install it first; see docs/development.md",
                self.program
            ))
        } else {
            XtaskError::io(format!("failed to start `{}`", self.display()), error)
        }
    }

    /// Run with inherited stdio. Fails on a non-zero exit status.
    pub fn run(&self) -> Result<()> {
        let status = self.build().status().map_err(|e| self.spawn_error(&e))?;
        if status.success() {
            Ok(())
        } else {
            Err(XtaskError::new(format!(
                "`{}` failed with {status}",
                self.display()
            )))
        }
    }

    /// Run and return stdout. Fails on a non-zero exit status.
    pub fn capture(&self) -> Result<String> {
        let output = self
            .build()
            .stdin(Stdio::null())
            .stderr(Stdio::inherit())
            .output()
            .map_err(|e| self.spawn_error(&e))?;
        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).into_owned())
        } else {
            Err(XtaskError::new(format!(
                "`{}` failed with {}",
                self.display(),
                output.status
            )))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_joins_program_and_args() {
        let cmd = Cmd::new("cargo").args(["fmt", "--check"]);
        assert_eq!(cmd.display(), "cargo fmt --check");
    }

    #[test]
    fn missing_program_gives_install_hint() {
        let error = Cmd::new("fyrkat-no-such-program").run().unwrap_err();
        assert!(error.to_string().contains("was not found"), "{error}");
    }

    #[test]
    fn nonzero_exit_is_an_error() {
        let error = Cmd::new("sh").args(["-c", "exit 3"]).run().unwrap_err();
        assert!(error.to_string().contains("failed with"), "{error}");
    }

    #[test]
    fn capture_returns_stdout() {
        let out = Cmd::new("sh")
            .args(["-c", "printf hello"])
            .capture()
            .unwrap();
        assert_eq!(out, "hello");
    }
}
