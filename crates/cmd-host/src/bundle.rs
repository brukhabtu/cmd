//! Running inside cmd.app, which carries uv in `Contents/MacOS` (decision 7).
//!
//! An app started from the Dock gets launchd's bare `PATH`, so a plugin's `uv run` would
//! find no uv, or someone else's, and whatever Python that uv chose. Inside the bundle the
//! plugins run on the bundle's uv instead, with one Python that uv fetched and keeps under
//! Application Support, so a plugin needs nothing else on the machine. Outside a bundle
//! (a developer's `cargo run`) nothing is set and plugins run on the developer's tools.

use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::host::{Host, Startup, Timeouts};
use crate::manifest::Located;

/// The Python every plugin runs on, as uv names it.
pub const PYTHON: &str = "3.15";

/// Where cmd.app keeps what it carries and what uv fetched for it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Bundle {
    /// `Contents/MacOS`, which holds the binary and the bundled uv.
    macos: PathBuf,
    /// `~/Library/Application Support/cmd`, which holds uv's Pythons and cache.
    support: PathBuf,
}

impl Bundle {
    /// The bundle `exe` runs from, if any. `exe` must be canonical: the cask links the
    /// binary from outside the bundle, and the link's own path would hide it.
    pub fn detect(exe: &Path, home: &Path) -> Option<Bundle> {
        let macos = exe.parent()?;
        let contents = macos.parent()?;
        let app = contents.parent()?;
        let is_bundle = macos.file_name() == Some(OsStr::new("MacOS"))
            && contents.file_name() == Some(OsStr::new("Contents"))
            && app.extension() == Some(OsStr::new("app"));
        is_bundle.then(|| Bundle {
            macos: macos.to_path_buf(),
            support: home.join("Library/Application Support/cmd"),
        })
    }

    /// The directory holding the binary and the bundled uv.
    pub fn macos(&self) -> &Path {
        &self.macos
    }

    /// The variables every plugin process (and the Python fetch) gets on top of the
    /// app's own: `PATH` led by the bundle, so `uv` is the bundled one, and uv told to
    /// use only the Pythons it manages, kept where the app keeps its own things.
    pub fn environment(&self, inherited_path: Option<&OsStr>) -> Vec<(OsString, OsString)> {
        let mut path = self.macos.clone().into_os_string();
        if let Some(inherited) = inherited_path.filter(|inherited| !inherited.is_empty()) {
            path.push(":");
            path.push(inherited);
        }
        vec![
            ("PATH".into(), path),
            (
                "UV_PYTHON_INSTALL_DIR".into(),
                self.support.join("python").into_os_string(),
            ),
            (
                "UV_CACHE_DIR".into(),
                self.support.join("uv-cache").into_os_string(),
            ),
            ("UV_PYTHON_PREFERENCE".into(), "only-managed".into()),
        ]
    }

    /// The command that fetches the plugins' Python. `--no-bin` keeps it off the
    /// person's own `PATH`: it is the app's Python, not theirs.
    pub fn python_install_command(&self) -> Vec<OsString> {
        let mut command = vec![self.macos.join("uv").into_os_string()];
        command.extend(["python", "install", PYTHON, "--no-bin"].map(OsString::from));
        command
    }

    /// Fetch the plugins' Python with `env`, unless uv already has it. uv's own words
    /// come back on failure, since they say whether it was the network or the disk.
    pub fn install_python(&self, env: &[(OsString, OsString)]) -> Result<(), String> {
        let command = self.python_install_command();
        let output = Command::new(&command[0])
            .args(&command[1..])
            .envs(env.iter().map(|(key, value)| (key, value)))
            .stdin(Stdio::null())
            .output()
            .map_err(|error| {
                format!(
                    "could not run {} to fetch Python {PYTHON}: {error}",
                    command[0].to_string_lossy()
                )
            })?;
        if output.status.success() {
            return Ok(());
        }
        let said = String::from_utf8_lossy(&output.stderr);
        let said = said.trim();
        Err(if said.is_empty() {
            format!("could not fetch Python {PYTHON}: uv {}", output.status)
        } else {
            format!("could not fetch Python {PYTHON}: {said}")
        })
    }
}

/// [`Host::start_reporting`] for the app: inside a bundle, the Python is fetched before
/// the first plugin starts and every plugin runs with [`Bundle::environment`]; outside
/// one, this is [`Host::start_reporting`] itself.
pub fn start_reporting(
    bundle: Option<&Bundle>,
    inherited_path: Option<&OsStr>,
    plugins: Vec<Located>,
    timeouts: Timeouts,
    mut report: impl FnMut(Startup),
) -> Host {
    let Some(bundle) = bundle else {
        return Host::start_reporting(plugins, timeouts, report);
    };
    let env = bundle.environment(inherited_path);
    report(Startup::FetchingPython);
    report(Startup::FetchedPython(bundle.install_python(&env)));
    Host::start_reporting_in(plugins, timeouts, &env, report)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bundle() -> Bundle {
        Bundle::detect(
            Path::new("/Applications/cmd.app/Contents/MacOS/cmd"),
            Path::new("/Users/me"),
        )
        .expect("a binary in Contents/MacOS of an .app is in a bundle")
    }

    fn value<'a>(env: &'a [(OsString, OsString)], key: &str) -> Option<&'a OsStr> {
        env.iter()
            .find(|(name, _)| name == key)
            .map(|(_, value)| value.as_os_str())
    }

    #[test]
    fn a_binary_in_contents_macos_of_an_app_is_in_a_bundle() {
        let bundle = bundle();
        assert_eq!(
            bundle.macos(),
            Path::new("/Applications/cmd.app/Contents/MacOS")
        );
        assert_eq!(
            bundle.support,
            Path::new("/Users/me/Library/Application Support/cmd")
        );
    }

    #[test]
    fn anywhere_else_is_not_a_bundle() {
        let home = Path::new("/Users/me");
        for exe in [
            "/Users/me/cmd/target/debug/cmd",
            "/opt/homebrew/bin/cmd",
            "/Applications/cmd.app/MacOS/cmd",
            "/Applications/cmd/Contents/MacOS/cmd",
            "/Applications/cmd.app/Contents/Resources/cmd",
            "cmd",
            "/",
        ] {
            assert_eq!(Bundle::detect(Path::new(exe), home), None, "{exe}");
        }
    }

    #[test]
    fn the_bundle_leads_the_path_and_uv_keeps_its_pythons_with_the_app() {
        let env = bundle().environment(Some(OsStr::new("/usr/bin:/bin")));
        assert_eq!(
            value(&env, "PATH"),
            Some(OsStr::new(
                "/Applications/cmd.app/Contents/MacOS:/usr/bin:/bin"
            ))
        );
        assert_eq!(
            value(&env, "UV_PYTHON_INSTALL_DIR"),
            Some(OsStr::new(
                "/Users/me/Library/Application Support/cmd/python"
            ))
        );
        assert_eq!(
            value(&env, "UV_CACHE_DIR"),
            Some(OsStr::new(
                "/Users/me/Library/Application Support/cmd/uv-cache"
            ))
        );
        assert_eq!(
            value(&env, "UV_PYTHON_PREFERENCE"),
            Some(OsStr::new("only-managed"))
        );
    }

    #[test]
    fn without_an_inherited_path_the_bundle_is_the_whole_path() {
        for inherited in [None, Some(OsStr::new(""))] {
            let env = bundle().environment(inherited);
            assert_eq!(
                value(&env, "PATH"),
                Some(OsStr::new("/Applications/cmd.app/Contents/MacOS"))
            );
        }
    }

    #[test]
    fn the_fetch_uses_the_bundled_uv_and_leaves_the_person_s_path_alone() {
        assert_eq!(
            bundle().python_install_command(),
            [
                "/Applications/cmd.app/Contents/MacOS/uv",
                "python",
                "install",
                "3.15",
                "--no-bin"
            ]
            .map(OsString::from)
        );
    }
}
