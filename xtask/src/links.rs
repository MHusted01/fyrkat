//! Internal Markdown link checking: relative file links and heading anchors.
//!
//! External links (anything with a URL scheme) are not fetched. Network access would make
//! the check flaky, and external rot is a separate concern.

use crate::error::{Result, XtaskError};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::Path;

/// A link destination and the 1-based line it appears on.
#[derive(Debug, PartialEq, Eq)]
pub struct Link {
    pub line: usize,
    pub target: String,
}

/// Replace the contents of inline code spans with spaces so links inside them are ignored.
fn blank_code_spans(line: &str) -> String {
    let mut in_code = false;
    line.chars()
        .map(|c| {
            if c == '`' {
                in_code = !in_code;
                ' '
            } else if in_code {
                ' '
            } else {
                c
            }
        })
        .collect()
}

/// Parse the destination that follows `](` or `]:`.
fn parse_destination(rest: &str) -> Option<String> {
    let rest = rest.trim_start();
    if let Some(inner) = rest.strip_prefix('<') {
        return inner
            .find('>')
            .and_then(|end| inner.get(..end))
            .map(str::to_owned);
    }
    let mut depth = 0usize;
    let mut end = rest.len();
    for (index, c) in rest.char_indices() {
        match c {
            '(' => depth += 1,
            ')' if depth > 0 => depth -= 1,
            ')' => {
                end = index;
                break;
            }
            c if c.is_whitespace() => {
                end = index;
                break;
            }
            _ => {}
        }
    }
    rest.get(..end).filter(|d| !d.is_empty()).map(str::to_owned)
}

/// The text after `]:` if the line is a reference definition such as `[id]: target`.
fn reference_definition(trimmed: &str) -> Option<&str> {
    let inner = trimmed.strip_prefix('[')?;
    let (label, rest) = inner.split_once("]:")?;
    (!label.contains(']')).then_some(rest)
}

fn is_fence(line: &str) -> bool {
    let trimmed = line.trim_start();
    trimmed.starts_with("```") || trimmed.starts_with("~~~")
}

/// Every inline link and reference definition outside code fences and code spans.
pub fn extract_links(markdown: &str) -> Vec<Link> {
    let mut links = Vec::new();
    let mut in_fence = false;
    for (index, raw) in markdown.lines().enumerate() {
        if is_fence(raw) {
            in_fence = !in_fence;
            continue;
        }
        if in_fence {
            continue;
        }
        let line = blank_code_spans(raw);
        let trimmed = line.trim_start();
        if let Some(rest) = reference_definition(trimmed) {
            links.extend(parse_destination(rest).map(|target| Link {
                line: index + 1,
                target,
            }));
            continue;
        }
        for (position, _) in line.match_indices("](") {
            let rest = line.get(position + 2..).unwrap_or_default();
            if let Some(target) = parse_destination(rest) {
                links.push(Link {
                    line: index + 1,
                    target,
                });
            }
        }
    }
    links
}

/// Whether the target has a URL scheme (`https:`, `mailto:`) or is protocol-relative.
pub fn is_external(target: &str) -> bool {
    if target.starts_with("//") {
        return true;
    }
    match target.split_once(':') {
        Some((scheme, _)) => {
            !scheme.is_empty()
                && scheme
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || "+.-".contains(c))
                && scheme.starts_with(|c: char| c.is_ascii_alphabetic())
        }
        None => false,
    }
}

/// The anchor GitHub generates for a heading.
pub fn slug(heading: &str) -> String {
    heading
        .trim()
        .to_lowercase()
        .chars()
        .filter_map(|c| match c {
            ' ' => Some('-'),
            c if c.is_alphanumeric() || c == '-' || c == '_' => Some(c),
            _ => None,
        })
        .collect()
}

/// All heading anchors in a document, with GitHub's `-1`, `-2` suffixes for repeats.
pub fn heading_slugs(markdown: &str) -> HashSet<String> {
    let mut seen: HashMap<String, usize> = HashMap::new();
    let mut slugs = HashSet::new();
    let mut in_fence = false;
    for line in markdown.lines() {
        if is_fence(line) {
            in_fence = !in_fence;
            continue;
        }
        let hashes = line.chars().take_while(|&c| c == '#').count();
        let Some(title) = line.get(hashes..).and_then(|t| t.strip_prefix(' ')) else {
            continue;
        };
        if in_fence || hashes == 0 || hashes > 6 {
            continue;
        }
        let base = slug(title.trim_end_matches('#'));
        let count = seen.entry(base.clone()).or_insert(0);
        slugs.insert(if *count == 0 {
            base
        } else {
            format!("{base}-{count}")
        });
        *count += 1;
    }
    slugs
}

/// Resolve `path` against the directory of `from_file`. `None` if it leaves the repository.
pub fn resolve(from_file: &str, path: &str) -> Option<String> {
    let mut parts: Vec<&str> = Vec::new();
    if !path.starts_with('/') {
        parts.extend(from_file.split('/'));
        parts.pop();
    }
    for segment in path.split('/') {
        match segment {
            "" | "." => {}
            ".." => {
                parts.pop()?;
            }
            other => parts.push(other),
        }
    }
    Some(parts.join("/"))
}

/// Every file path plus every directory that contains one, plus the root (empty string).
pub fn known_paths(files: &[String]) -> HashSet<String> {
    let mut known = HashSet::from([String::new()]);
    for file in files {
        known.insert(file.clone());
        let mut dir = file.as_str();
        while let Some((parent, _)) = dir.rsplit_once('/') {
            known.insert(parent.to_owned());
            dir = parent;
        }
    }
    known
}

fn check_link(
    from: &str,
    link: &Link,
    known: &HashSet<String>,
    docs: &BTreeMap<String, String>,
) -> Option<String> {
    if link.target.starts_with("//") || is_external(&link.target) {
        return None;
    }
    let (path, fragment) = link
        .target
        .split_once('#')
        .unwrap_or((link.target.as_str(), ""));
    let destination = if path.is_empty() {
        from.to_owned()
    } else {
        let Some(resolved) = resolve(from, path) else {
            return Some(format!(
                "{from}:{}: link leaves the repository: {}",
                link.line, link.target
            ));
        };
        resolved
    };
    if !known.contains(&destination) {
        return Some(format!(
            "{from}:{}: broken link, no such path: {}",
            link.line, link.target
        ));
    }
    let anchors = docs.get(&destination).filter(|_| !fragment.is_empty())?;
    (!heading_slugs(anchors).contains(&fragment.to_lowercase())).then(|| {
        format!(
            "{from}:{}: no such heading anchor: {}",
            link.line, link.target
        )
    })
}

/// Describe every broken internal link in `docs` (path to contents).
pub fn find_broken(known: &HashSet<String>, docs: &BTreeMap<String, String>) -> Vec<String> {
    let mut problems = Vec::new();
    for (path, text) in docs {
        for link in extract_links(text) {
            problems.extend(check_link(path, &link, known, docs));
        }
    }
    problems
}

/// Check every Markdown file among `repo_files`.
pub fn check(root: &Path, repo_files: &[String]) -> Result<()> {
    let mut docs = BTreeMap::new();
    for path in repo_files
        .iter()
        .filter(|p| crate::repo::has_extension(p, "md"))
    {
        let text = std::fs::read_to_string(root.join(path))
            .map_err(|e| XtaskError::io(format!("reading {path}"), &e))?;
        docs.insert(path.clone(), text);
    }
    let problems = find_broken(&known_paths(repo_files), &docs);
    if problems.is_empty() {
        Ok(())
    } else {
        Err(XtaskError::new(format!(
            "broken Markdown links:\n  {}",
            problems.join("\n  ")
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn targets(markdown: &str) -> Vec<String> {
        extract_links(markdown)
            .into_iter()
            .map(|l| l.target)
            .collect()
    }

    #[test]
    fn extracts_inline_and_reference_links() {
        let md = "See [a](a.md) and [b](<b c.md> \"t\").\n\n[ref]: docs/r.md\n";
        assert_eq!(targets(md), vec!["a.md", "b c.md", "docs/r.md"]);
    }

    #[test]
    fn ignores_fences_and_code_spans() {
        let md = "`[x](no.md)` text\n```\n[y](no.md)\n```\n[z](yes.md)\n";
        assert_eq!(targets(md), vec!["yes.md"]);
    }

    #[test]
    fn keeps_balanced_parentheses_in_targets() {
        assert_eq!(targets("[a](x_(y).md)"), vec!["x_(y).md"]);
    }

    #[test]
    fn classifies_external_targets() {
        assert!(is_external("https://example.com"));
        assert!(is_external("mailto:a@b.c"));
        assert!(!is_external("docs/a.md"));
        assert!(!is_external("a.md#x:y"));
    }

    #[test]
    fn slugs_follow_github_rules() {
        assert_eq!(slug("Hello, World! (v2)"), "hello-world-v2");
        let md = "# A\n## A\n```\n# hidden\n```\n";
        let slugs = heading_slugs(md);
        assert!(slugs.contains("a") && slugs.contains("a-1") && !slugs.contains("hidden"));
    }

    #[test]
    fn resolves_relative_paths() {
        assert_eq!(
            resolve("docs/a.md", "../README.md").as_deref(),
            Some("README.md")
        );
        assert_eq!(
            resolve("docs/a.md", "b/c.md").as_deref(),
            Some("docs/b/c.md")
        );
        assert_eq!(resolve("a.md", "/docs/x.md").as_deref(), Some("docs/x.md"));
        assert_eq!(resolve("a.md", "../x.md"), None);
    }

    fn run(files: &[(&str, &str)]) -> Vec<String> {
        let names: Vec<String> = files.iter().map(|(p, _)| (*p).to_owned()).collect();
        let docs = files
            .iter()
            .filter(|(p, _)| crate::repo::has_extension(p, "md"))
            .map(|(p, t)| ((*p).to_owned(), (*t).to_owned()))
            .collect();
        find_broken(&known_paths(&names), &docs)
    }

    #[test]
    fn valid_links_pass() {
        let problems = run(&[
            (
                "README.md",
                "[d](docs/) [a](docs/a.md#title) [s](#top)\n# Top\n",
            ),
            ("docs/a.md", "# Title\n[up](../README.md)\n"),
        ]);
        assert!(problems.is_empty(), "{problems:?}");
    }

    #[test]
    fn broken_file_and_anchor_are_reported() {
        let problems = run(&[
            ("README.md", "[gone](docs/gone.md)\n[bad](docs/a.md#nope)\n"),
            ("docs/a.md", "# Title\n"),
        ]);
        assert_eq!(problems.len(), 2, "{problems:?}");
        assert!(problems[0].starts_with("README.md:1:"));
        assert!(problems[1].contains("no such heading anchor"));
    }
}
