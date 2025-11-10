// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::process::{Command, Stdio};
use tauri::Manager;

#[derive(Debug, Serialize, Deserialize)]
struct Config {
    series: Vec<Series>,
    download_path: String,
    archive_file: String,
    debug: bool,
    yt_dlp_options: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Series {
    name: String,
    url: String,
    enabled: bool,
    include_patterns: Vec<String>,
    exclude_patterns: Vec<String>,
    thumbnail_url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct Episode {
    url: String,
    title: String,
    id: String,
}

#[derive(Debug, Serialize)]
struct DownloadProgress {
    series_name: String,
    episode_title: String,
    status: String,
    progress: f32,
}

// Check VPN connection
#[tauri::command]
async fn check_vpn() -> Result<String, String> {
    let client = reqwest::Client::new();
    
    // Try multiple services
    let services = vec![
        "https://ipapi.co/json/",
        "https://ip.seeip.org/geoip",
    ];
    
    for service in services {
        if let Ok(response) = client.get(service).send().await {
            if let Ok(data) = response.json::<serde_json::Value>().await {
                let country = data.get("country_code")
                    .or_else(|| data.get("cc"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                
                let ip = data.get("ip")
                    .and_then(|v| v.as_str())
                    .unwrap_or("unknown");
                
                if country == "JP" {
                    return Ok(format!("Connected via Japan IP ({})", ip));
                } else {
                    return Err(format!("Not connected to Japan VPN (detected: {}, IP: {})", country, ip));
                }
            }
        }
    }
    
    Err("Could not verify VPN connection".to_string())
}

// Load configuration
#[tauri::command]
async fn load_config(app_handle: tauri::AppHandle) -> Result<Config, String> {
    let app_dir = app_handle.path_resolver()
        .app_data_dir()
        .ok_or("Could not get app data directory")?;
    
    let config_path = app_dir.join("config.json");
    
    if !config_path.exists() {
        // Create default config
        let default_config = Config {
            series: vec![],
            download_path: app_dir.join("downloads").to_string_lossy().to_string(),
            archive_file: "downloaded.txt".to_string(),
            debug: false,
            yt_dlp_options: vec![
                "-o".to_string(),
                "%(series)s/%(title)s.%(ext)s".to_string(),
                "--write-sub".to_string(),
                "--sub-lang".to_string(),
                "ja".to_string(),
            ],
        };
        
        std::fs::create_dir_all(&app_dir).map_err(|e| e.to_string())?;
        let config_json = serde_json::to_string_pretty(&default_config).map_err(|e| e.to_string())?;
        std::fs::write(&config_path, config_json).map_err(|e| e.to_string())?;
        
        return Ok(default_config);
    }
    
    let config_str = std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
    let config: Config = serde_json::from_str(&config_str).map_err(|e| e.to_string())?;
    
    Ok(config)
}

// Save configuration
#[tauri::command]
async fn save_config(app_handle: tauri::AppHandle, config: Config) -> Result<(), String> {
    let app_dir = app_handle.path_resolver()
        .app_data_dir()
        .ok_or("Could not get app data directory")?;
    
    let config_path = app_dir.join("config.json");
    let config_json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(&config_path, config_json).map_err(|e| e.to_string())?;
    
    Ok(())
}

// Get Python script path
fn get_python_script_path(app_handle: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    let resource_path = app_handle.path_resolver()
        .resolve_resource("python/tver_downloader.py")
        .ok_or("Could not find Python script")?;
    
    Ok(resource_path)
}

// Fetch episodes for a series
#[tauri::command]
async fn fetch_episodes(app_handle: tauri::AppHandle, series_url: String) -> Result<Vec<Episode>, String> {
    let script_path = get_python_script_path(&app_handle)?;
    
    // Call Python script to get episodes
    let output = Command::new("python3")
        .arg(&script_path)
        .arg("--fetch-episodes")
        .arg(&series_url)
        .output()
        .map_err(|e| format!("Failed to execute Python script: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let episodes: Vec<Episode> = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse episodes: {}", e))?;
    
    Ok(episodes)
}

// Download episodes
#[tauri::command]
async fn download_episodes(
    app_handle: tauri::AppHandle,
    window: tauri::Window,
    config: Config,
) -> Result<String, String> {
    let script_path = get_python_script_path(&app_handle)?;
    let app_dir = app_handle.path_resolver()
        .app_data_dir()
        .ok_or("Could not get app data directory")?;
    
    let config_path = app_dir.join("config.json");
    
    // Start Python script
    let mut child = Command::new("python3")
        .arg(&script_path)
        .arg("--config")
        .arg(&config_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start download: {}", e))?;
    
    // Stream output to frontend
    if let Some(stdout) = child.stdout.take() {
        use std::io::{BufRead, BufReader};
        let reader = BufReader::new(stdout);
        
        for line in reader.lines() {
            if let Ok(line) = line {
                // Emit progress events to frontend
                let _ = window.emit("download-progress", line.clone());
            }
        }
    }
    
    let status = child.wait().map_err(|e| e.to_string())?;
    
    if status.success() {
        Ok("Download completed successfully".to_string())
    } else {
        Err("Download failed".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            check_vpn,
            load_config,
            save_config,
            fetch_episodes,
            download_episodes,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}