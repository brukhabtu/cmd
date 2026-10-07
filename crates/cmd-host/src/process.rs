//! One plugin process and the request/response discipline over its pipes.

use std::io::{self, BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::time::{Duration, Instant};

use cmd_core::protocol::{self, DecodeError, Method, Request};
use serde::de::DeserializeOwned;
use thiserror::Error;

/// A running plugin. Dropping it kills the process.
pub struct PluginProcess {
    child: Child,
    stdin: ChildStdin,
    lines: Receiver<io::Result<String>>,
    next_id: u64,
}

/// Why a call to a plugin did not produce its result.
#[derive(Debug, Error)]
pub enum CallError {
    #[error("could not write to the plugin: {0}")]
    Write(#[source] io::Error),
    #[error("could not read from the plugin: {0}")]
    Read(#[source] io::Error),
    #[error("the plugin exited")]
    Exited,
    #[error("no answer within {0:?}")]
    Timeout(Duration),
    #[error(
        "the plugin wrote a line that is not a protocol message (stdout is reserved for the \
         protocol; log to stderr instead): {line:?}"
    )]
    NotProtocol { line: String },
    #[error(transparent)]
    Decode(#[from] DecodeError),
}

impl PluginProcess {
    /// Start `command` in `cwd` with stdin and stdout piped. Stderr is inherited, so a
    /// plugin's logs reach the host's stderr.
    pub fn spawn(command: &[String], cwd: &Path) -> io::Result<Self> {
        let (program, args) = command
            .split_first()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "empty command"))?;
        let mut child = Command::new(program)
            .args(args)
            .current_dir(cwd)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let (Some(stdin), Some(stdout)) = (child.stdin.take(), child.stdout.take()) else {
            return Err(io::Error::other("the child's pipes were not opened"));
        };
        let (sender, lines) = mpsc::channel();
        std::thread::Builder::new()
            .name(format!("plugin-stdout:{program}"))
            .spawn(move || {
                let mut reader = BufReader::new(stdout);
                loop {
                    let mut line = String::new();
                    match reader.read_line(&mut line) {
                        Ok(0) => break,
                        Ok(_) => {
                            if sender.send(Ok(line)).is_err() {
                                break;
                            }
                        }
                        Err(error) => {
                            let _ = sender.send(Err(error));
                            break;
                        }
                    }
                }
            })?;
        Ok(Self {
            child,
            stdin,
            lines,
            next_id: 1,
        })
    }

    /// Send one request and wait for its answer.
    ///
    /// Answers to earlier requests that arrive late are dropped: by then the
    /// launcher has moved on.
    pub fn call<T: DeserializeOwned>(
        &mut self,
        method: Method,
        timeout: Duration,
    ) -> Result<T, CallError> {
        let id = self.next_id;
        self.next_id += 1;
        let line = protocol::encode_request(&Request { id, method });
        self.stdin
            .write_all(line.as_bytes())
            .and_then(|()| self.stdin.flush())
            .map_err(CallError::Write)?;
        let deadline = Instant::now() + timeout;
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            let line = match self.lines.recv_timeout(remaining) {
                Ok(Ok(line)) => line,
                Ok(Err(error)) => return Err(CallError::Read(error)),
                Err(RecvTimeoutError::Timeout) => return Err(CallError::Timeout(timeout)),
                Err(RecvTimeoutError::Disconnected) => return Err(CallError::Exited),
            };
            let response = match protocol::decode_response(&line) {
                Ok(response) => response,
                Err(DecodeError::Json(_)) => {
                    return Err(CallError::NotProtocol {
                        line: line.trim_end().to_string(),
                    });
                }
                Err(error) => return Err(error.into()),
            };
            if response.id != id {
                continue;
            }
            return Ok(protocol::result(response)?);
        }
    }
}

impl Drop for PluginProcess {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
