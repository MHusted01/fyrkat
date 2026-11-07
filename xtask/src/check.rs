//! `cargo xtask check`: the single local verification command. CI runs exactly this.

use crate::error::{Result, XtaskError};
use crate::process::Cmd;
use crate::tools::{TOOLS, Tool, path_with_tools, verify};
use crate::{isolation, links, repo};
use std::ffi::OsString;
use std::path::PathBuf;

const UEFI_TARGETS: [&str; 2] = ["aarch64-unknown-uefi", "x86_64-unknown-uefi"];
const HOOK_TESTS: &str = ".claude/hooks/test-hooks.sh";

/// Shared inputs for every step.
struct Ctx {
    root: PathBuf,
    files: Vec<String>,
    path: OsString,
}

struct Step {
    name: &'static str,
    run: fn(&Ctx) -> Result<()>,
}

const STEPS: &[Step] = &[
    Step {
        name: "rustfmt",
        run: rustfmt,
    },
    Step {
        name: "clippy (host)",
        run: clippy_host,
    },
    Step {
        name: "clippy boot-smoke aarch64-unknown-uefi",
        run: |c| clippy_uefi(c, UEFI_TARGETS[0]),
    },
    Step {
        name: "clippy boot-smoke x86_64-unknown-uefi",
        run: |c| clippy_uefi(c, UEFI_TARGETS[1]),
    },
    Step {
        name: "cargo-nextest",
        run: nextest,
    },
    Step {
        name: "rustdoc",
        run: rustdoc,
    },
    Step {
        name: "cargo-deny",
        run: deny,
    },
    Step {
        name: "shellcheck",
        run: shellcheck,
    },
    Step {
        name: "hook tests",
        run: hook_tests,
    },
    Step {
        name: "actionlint",
        run: actionlint,
    },
    Step {
        name: "markdown links",
        run: markdown_links,
    },
    Step {
        name: "spike isolation",
        run: spike_isolation,
    },
];

fn cargo(ctx: &Ctx, args: &[&str]) -> Cmd {
    Cmd::new("cargo")
        .args(args.iter().copied())
        .dir(&ctx.root)
        .env("PATH", ctx.path.clone())
}

fn rustfmt(ctx: &Ctx) -> Result<()> {
    cargo(ctx, &["fmt", "--all", "--", "--check"]).run()
}

fn clippy_host(ctx: &Ctx) -> Result<()> {
    cargo(ctx, &["clippy", "--all-targets", "--", "-D", "warnings"]).run()
}

fn clippy_uefi(ctx: &Ctx, target: &str) -> Result<()> {
    let args = [
        "clippy",
        "--package",
        "boot-smoke",
        "--target",
        target,
        "--",
        "-D",
        "warnings",
    ];
    cargo(ctx, &args).run()
}

fn require_tool(ctx: &Ctx, crate_name: &str) -> Result<&'static Tool> {
    let tool = TOOLS
        .iter()
        .find(|t| t.crate_name == crate_name)
        .ok_or_else(|| XtaskError::new(format!("{crate_name} is not in the pinned tool table")))?;
    verify(&ctx.root, tool)?;
    Ok(tool)
}

fn nextest(ctx: &Ctx) -> Result<()> {
    require_tool(ctx, "cargo-nextest")?;
    cargo(ctx, &["nextest", "run", "--no-tests=fail"]).run()
}

fn rustdoc(ctx: &Ctx) -> Result<()> {
    cargo(ctx, &["doc", "--no-deps", "--document-private-items"])
        .env("RUSTDOCFLAGS", "-D warnings")
        .run()
}

fn deny(ctx: &Ctx) -> Result<()> {
    require_tool(ctx, "cargo-deny")?;
    cargo(ctx, &["deny", "--all-features", "check"]).run()
}

fn files_matching(ctx: &Ctx, accept: impl Fn(&str) -> bool) -> Vec<String> {
    ctx.files.iter().filter(|f| accept(f)).cloned().collect()
}

fn shellcheck(ctx: &Ctx) -> Result<()> {
    let scripts = files_matching(ctx, |f| repo::has_extension(f, "sh"));
    if scripts.is_empty() {
        return Ok(());
    }
    Cmd::new("shellcheck").args(scripts).dir(&ctx.root).run()
}

fn hook_tests(ctx: &Ctx) -> Result<()> {
    if !ctx.root.join(HOOK_TESTS).is_file() {
        return Err(XtaskError::new(format!("{HOOK_TESTS} is missing")));
    }
    Cmd::new("bash").args([HOOK_TESTS]).dir(&ctx.root).run()
}

fn actionlint(ctx: &Ctx) -> Result<()> {
    let workflows = files_matching(ctx, |f| {
        f.starts_with(".github/workflows/")
            && (repo::has_extension(f, "yml") || repo::has_extension(f, "yaml"))
    });
    if workflows.is_empty() {
        return Ok(());
    }
    Cmd::new("actionlint").args(workflows).dir(&ctx.root).run()
}

fn markdown_links(ctx: &Ctx) -> Result<()> {
    links::check(&ctx.root, &ctx.files)
}

fn spike_isolation(ctx: &Ctx) -> Result<()> {
    isolation::check(&ctx.root, &ctx.files)
}

/// Run every step, report each result, and fail if any step failed.
pub fn run() -> Result<()> {
    let root = repo::root()?;
    let ctx = Ctx {
        files: repo::files(&root)?,
        path: path_with_tools(&root)?,
        root,
    };
    let mut failed = Vec::new();
    for step in STEPS {
        println!("\n==> {}", step.name);
        match (step.run)(&ctx) {
            Ok(()) => println!("PASS {}", step.name),
            Err(error) => {
                println!("FAIL {}: {error}", step.name);
                failed.push(step.name);
            }
        }
    }
    summarize(&failed)
}

fn summarize(failed: &[&str]) -> Result<()> {
    println!();
    if failed.is_empty() {
        println!("check: all {} steps passed", STEPS.len());
        Ok(())
    } else {
        Err(XtaskError::new(format!(
            "check: {} of {} steps failed: {}",
            failed.len(),
            STEPS.len(),
            failed.join(", ")
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn step_names_are_unique() {
        let mut names: Vec<_> = STEPS.iter().map(|s| s.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), STEPS.len());
    }

    #[test]
    fn summary_lists_failures() {
        let error = summarize(&["rustfmt", "rustdoc"]).unwrap_err();
        assert!(error.to_string().contains("2 of"), "{error}");
        assert!(error.to_string().contains("rustfmt, rustdoc"), "{error}");
        assert!(summarize(&[]).is_ok());
    }

    #[test]
    fn every_pinned_tool_is_used_by_a_step() {
        for tool in TOOLS {
            assert!(
                matches!(tool.crate_name, "cargo-nextest" | "cargo-deny"),
                "{} has no check step",
                tool.crate_name
            );
        }
    }
}
