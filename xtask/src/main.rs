//! Fyrkat task runner. Standard library only, by policy.
#![forbid(unsafe_code)]

mod boot;
mod check;
mod cli;
mod error;
mod isolation;
mod links;
mod process;
mod qemu;
mod repo;
mod tools;

use cli::Command;
use error::Result;
use std::process::ExitCode;

fn run(args: &[String]) -> Result<()> {
    match cli::parse(args)? {
        Command::Help => {
            print!("{}", cli::USAGE);
            Ok(())
        }
        Command::Tools => tools::install(&repo::root()?),
        Command::Check => check::run(),
        Command::Boot(options) => boot::run(&repo::root()?, &options),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
