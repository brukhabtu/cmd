# Install

cmd runs on Macs with Apple silicon, macOS 12 or later.

## From a CI build

Until there is a signed release, every push builds `cmd.app` and attaches it to the CI run.

1. Open the repository's **Actions** tab, pick the latest successful **ci** run on the
   default branch, and download the **cmd.app** artifact.
2. Unzip it and move `cmd.app` to `/Applications`.
3. The build is not signed yet, so macOS quarantines it. Clear that once:

    ```sh
    xattr -dr com.apple.quarantine /Applications/cmd.app
    ```

4. Open it. There is no Dock icon and no menu bar: cmd lives behind its hotkey,
   ++option+space++.

## The first launch

On its first launch cmd fetches the Python its plugins run on, once, into
`~/Library/Application Support/cmd/`. The line under the input says so while it happens,
and it needs the network that one time.

!!! abstract "To be written"
    A signed, notarised release and a Homebrew cask, starting at login, and changing the
    hotkey. Tracked by the documentation epic (TASK-1.43) and TASK-1.25.
