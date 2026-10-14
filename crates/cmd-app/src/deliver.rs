//! Telling the person about a notice a plugin sent (decision 13).

use cmd_core::notice::Notice;

/// Post `notice` as a macOS notification.
///
/// This is the seam TASK-6.4 fills: it needs a Mac to build and to check how an unsigned
/// build is attributed (TASK-6.1), so until then the notice is only recorded in the recent
/// list, which the caller does first and whatever this does.
#[allow(
    clippy::missing_const_for_fn,
    reason = "a stub that TASK-6.4 fills with calls that are not const"
)]
pub fn deliver(_notice: &Notice) {}
