fn main() {
    // Let tauri-build generate the context into OUT_DIR so tauri::generate_context!() works.
    // This is required for `tauri::generate_context!()` used in src/main.rs.
    tauri_build::build();
}