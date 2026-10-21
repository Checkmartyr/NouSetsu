# GLib 0.18.5 security backport

This directory contains the crates.io `glib` 0.18.5 source, including its
original MIT license and copyright notices. Cargo's `[patch.crates-io]` in
`src-tauri/Cargo.toml` replaces the registry crate for the entire desktop
dependency graph.

## RUSTSEC-2024-0429 / GHSA-wrw7-89jp-8q8g

`VariantStrIter::impl_get` passed an immutable reference to an output pointer
that GLib mutates. Optimized builds can discard the write and dereference a
null pointer. The only production source changes are the two lines from
[upstream PR #1343](https://github.com/gtk-rs/gtk-rs-core/pull/1343): declare
`p` mutable and pass `&mut p` to `g_variant_get_child`.

The version stays 0.18.5 to satisfy Tauri's GTK 0.18 dependency family. This is
a source backport, not a claim that the registry release is fixed. The
[RustSec advisory](https://rustsec.org/advisories/RUSTSEC-2024-0429.html)
lists registry versions starting at 0.20.0 as patched, so version-based
scanners may continue reporting this advisory. No advisory is suppressed.

## Verification

On Linux, install `libglib2.0-dev`, then run from the repository root:

```sh
cargo test --manifest-path src-tauri/vendor/glib/Cargo.toml --release --lib variant_iter::tests
cargo tree --manifest-path src-tauri/Cargo.toml --locked --target x86_64-unknown-linux-gnu -i glib
```

Release mode matters: the original undefined behavior is exposed by compiler
optimization. The upstream iterator tests cover the string iterator's `next`,
`nth`, `nth_back`, and `last` paths. A local regression also covers nonempty
`next_back`. CI runs these tests on Linux. Windows desktop checks alone do
not compile the affected Linux dependency.

Verified with Rust 1.93 on Debian Bookworm: removing the two-line fix causes
the optimized iterator tests to terminate with SIGSEGV (Cargo exit 101).
Restoring it passes all 12 iterator tests, including the local regression.
The desktop Linux dependency tree resolves GLib exclusively to this directory;
the Windows desktop `cargo check --locked --offline` also passes.

## Removal

Remove the patch and this directory once Tauri's full GTK dependency family
accepts a fixed upstream GLib release. Regenerate `src-tauri/Cargo.lock`,
verify the Linux dependency tree contains no vulnerable GLib version, and
rerun the desktop checks. Do not change only the lockfile version or add a
second, unused GLib dependency.
