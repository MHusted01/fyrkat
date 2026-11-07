//! The single error type for the task runner.

use std::fmt;

/// A failure with a message that is safe to show to the user as is.
#[derive(Debug, PartialEq, Eq)]
pub struct XtaskError {
    message: String,
}

impl XtaskError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }

    /// Wrap an I/O error with what was being attempted.
    pub fn io(context: impl fmt::Display, source: &std::io::Error) -> Self {
        Self::new(format!("{context}: {source}"))
    }
}

impl fmt::Display for XtaskError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for XtaskError {}

pub type Result<T> = std::result::Result<T, XtaskError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn io_error_keeps_context_and_cause() {
        let cause = std::io::Error::new(std::io::ErrorKind::NotFound, "gone");
        let error = XtaskError::io("reading file", &cause);
        assert_eq!(error.to_string(), "reading file: gone");
    }
}
