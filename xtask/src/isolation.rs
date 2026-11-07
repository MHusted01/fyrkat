//! Spike isolation: no Cargo manifest outside `spikes/` may refer to `spikes/`.

use crate::error::{Result, XtaskError};
use std::path::Path;

const SPIKES_DIR: &str = "spikes/";

fn is_outside_manifest(path: &str) -> bool {
    let is_manifest = path.rsplit('/').next() == Some("Cargo.toml");
    is_manifest && !path.starts_with(SPIKES_DIR)
}

/// Strip a TOML comment. Good enough here: manifests do not hold `#` inside paths.
fn strip_comment(line: &str) -> &str {
    line.split('#').next().unwrap_or(line)
}

/// Describe every reference to `spikes/` in manifests outside `spikes/`.
///
/// `files` pairs a repository-relative path with its contents.
pub fn violations(files: &[(String, String)]) -> Vec<String> {
    let mut found = Vec::new();
    for (path, text) in files.iter().filter(|(p, _)| is_outside_manifest(p)) {
        for (index, line) in text.lines().enumerate() {
            if strip_comment(line).contains(SPIKES_DIR) {
                found.push(format!("{path}:{}: refers to {SPIKES_DIR}", index + 1));
            }
        }
    }
    found
}

/// Run the check over the repository's files.
pub fn check(root: &Path, repo_files: &[String]) -> Result<()> {
    let mut manifests = Vec::new();
    for path in repo_files.iter().filter(|p| is_outside_manifest(p)) {
        let text = std::fs::read_to_string(root.join(path))
            .map_err(|e| XtaskError::io(format!("reading {path}"), &e))?;
        manifests.push((path.clone(), text));
    }
    let found = violations(&manifests);
    if found.is_empty() {
        Ok(())
    } else {
        Err(XtaskError::new(format!(
            "spike isolation violated:\n  {}",
            found.join("\n  ")
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn manifest(path: &str, text: &str) -> (String, String) {
        (path.to_owned(), text.to_owned())
    }

    #[test]
    fn dependency_on_a_spike_is_flagged() {
        let files = [manifest(
            "crates/kernel/Cargo.toml",
            "[dependencies]\nspike = { path = \"../../spikes/boot-latency\" }\n",
        )];
        let found = violations(&files);
        assert_eq!(found, vec!["crates/kernel/Cargo.toml:2: refers to spikes/"]);
    }

    #[test]
    fn workspace_member_in_spikes_is_flagged() {
        let files = [manifest(
            "Cargo.toml",
            "[workspace]\nmembers = [\"xtask\", \"spikes/a\"]\n",
        )];
        assert_eq!(violations(&files).len(), 1);
    }

    #[test]
    fn comments_and_unrelated_manifests_are_fine() {
        let files = [
            manifest(
                "Cargo.toml",
                "# spikes/ stays out of the workspace\n[workspace]\n",
            ),
            manifest("xtask/Cargo.toml", "[package]\nname = \"xtask\"\n"),
        ];
        assert_eq!(violations(&files), Vec::<String>::new());
    }

    #[test]
    fn manifests_inside_spikes_are_exempt() {
        let files = [manifest(
            "spikes/a/Cargo.toml",
            "x = { path = \"../../spikes/b\" }\n",
        )];
        assert_eq!(violations(&files), Vec::<String>::new());
    }

    #[test]
    fn only_cargo_manifests_are_inspected() {
        let files = [manifest("docs/notes.toml", "path = \"spikes/a\"\n")];
        assert_eq!(violations(&files), Vec::<String>::new());
    }
}
