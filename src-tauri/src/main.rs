// Entry point convention for Tauri v2 (`cargo tauri build` links this
// against the mobile-compatible lib crate) -- all real logic lives in
// lib.rs's run().
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    scilene_lib::run();
}
