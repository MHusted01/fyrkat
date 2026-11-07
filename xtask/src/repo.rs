//! Locating the repository root and listing its files.

use crate::error::{Result, XtaskError};
use crate::process::Cmd;
use std::path::{Path, PathBuf};

/// The repository root, derived from this crate's location at compile time.
pub fn root() -> Result<PathBuf> {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .ok_or_else(|| XtaskError::new("xtask manifest directory has no parent"))
}

/// Whether `path` ends in `.ext`, ignoring ASCII case.
pub fn has_extension(path: &str, ext: &str) -> bool {
    Path::new(path)
        .extension()
        .is_some_and(|e| e.eq_ignore_ascii_case(ext))
}

/// Every file Git tracks or would track (not ignored), relative to the root.
///
/// Uncommitted files are included so that `check` works before the first commit.
pub fn files(root: &Path) -> Result<Vec<String>> {
    let listing = Cmd::new("git")
        .args(["ls-files", "--cached", "--others", "--exclude-standard"])
        .dir(root)
        .capture()?;
    Ok(parse_listing(&listing)
        .into_iter()
        .filter(|f| root.join(f).is_file())
        .collect())
}

fn parse_listing(listing: &str) -> Vec<String> {
    let mut files: Vec<String> = listing
        .lines()
        .filter(|l| !l.is_empty())
        .map(str::to_owned)
        .collect();
    files.sort();
    files.dedup();
    files
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn listing_is_sorted_and_deduplicated() {
        assert_eq!(parse_listing("b\na\n\nb\n"), vec!["a", "b"]);
    }

    #[test]
    fn root_contains_workspace_manifest() {
        assert!(root().unwrap().join("Cargo.toml").is_file());
    }
}
