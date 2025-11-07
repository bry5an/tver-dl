import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { Plus, Play, Settings, Wifi, Download, Trash2, Edit2 } from 'lucide-react';

interface Series {
  name: string;
  url: string;
  enabled: boolean;
  include_patterns: string[];
  exclude_patterns: string[];
}

interface Config {
  series: Series[];
  download_path: string;
  archive_file: string;
  debug: boolean;
  yt_dlp_options: string[];
}

interface Episode {
  url: string;
  title: string;
  id: string;
}

function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [vpnStatus, setVpnStatus] = useState<string>('');
  const [isChecking, setIsChecking] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadLogs, setDownloadLogs] = useState<string[]>([]);
  const [showAddSeries, setShowAddSeries] = useState(false);
  const [editingSeries, setEditingSeries] = useState<Series | null>(null);
  const [selectedTab, setSelectedTab] = useState<'series' | 'settings' | 'logs'>('series');

  useEffect(() => {
    loadConfig();
    checkVPN();

    // Listen for download progress
    const unlisten = listen('download-progress', (event) => {
      setDownloadLogs(prev => [...prev, event.payload as string]);
    });

    return () => {
      unlisten.then(fn => fn());
    };
  }, []);

  const loadConfig = async () => {
    try {
      const cfg = await invoke<Config>('load_config');
      setConfig(cfg);
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const saveConfig = async (newConfig: Config) => {
    try {
      await invoke('save_config', { config: newConfig });
      setConfig(newConfig);
    } catch (error) {
      console.error('Failed to save config:', error);
    }
  };

  const checkVPN = async () => {
    setIsChecking(true);
    try {
      const status = await invoke<string>('check_vpn');
      setVpnStatus(`✓ ${status}`);
    } catch (error) {
      setVpnStatus(`✗ ${error}`);
    } finally {
      setIsChecking(false);
    }
  };

  const startDownload = async () => {
    if (!config) return;
    
    setIsDownloading(true);
    setDownloadLogs([]);
    
    try {
      await invoke('download_episodes', { config });
      setDownloadLogs(prev => [...prev, 'Download completed!']);
    } catch (error) {
      setDownloadLogs(prev => [...prev, `Error: ${error}`]);
    } finally {
      setIsDownloading(false);
    }
  };

  const toggleSeries = (index: number) => {
    if (!config) return;
    const newSeries = [...config.series];
    newSeries[index].enabled = !newSeries[index].enabled;
    saveConfig({ ...config, series: newSeries });
  };

  const deleteSeries = (index: number) => {
    if (!config) return;
    const newSeries = config.series.filter((_, i) => i !== index);
    saveConfig({ ...config, series: newSeries });
  };

  const addOrUpdateSeries = (series: Series) => {
    if (!config) return;
    
    if (editingSeries) {
      const index = config.series.findIndex(s => s.url === editingSeries.url);
      const newSeries = [...config.series];
      newSeries[index] = series;
      saveConfig({ ...config, series: newSeries });
    } else {
      saveConfig({ ...config, series: [...config.series, series] });
    }
    
    setShowAddSeries(false);
    setEditingSeries(null);
  };

  if (!config) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">TVer Downloader</h1>
            <p className="text-sm text-gray-400 mt-1">Automatic episode downloads from TVer</p>
          </div>
          
          <div className="flex items-center gap-4">
            <button
              onClick={checkVPN}
              disabled={isChecking}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
            >
              <Wifi className="w-4 h-4" />
              Check VPN
            </button>
            
            <button
              onClick={startDownload}
              disabled={isDownloading || config.series.filter(s => s.enabled).length === 0}
              className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" />
              {isDownloading ? 'Downloading...' : 'Download Episodes'}
            </button>
          </div>
        </div>
        
        {vpnStatus && (
          <div className={`mt-3 px-4 py-2 rounded-lg text-sm ${
            vpnStatus.startsWith('✓') ? 'bg-green-900/30 text-green-300' : 'bg-red-900/30 text-red-300'
          }`}>
            {vpnStatus}
          </div>
        )}
      </header>

      {/* Tabs */}
      <div className="bg-gray-800 border-b border-gray-700 px-6">
        <div className="flex gap-4">
          <button
            onClick={() => setSelectedTab('series')}
            className={`px-4 py-3 border-b-2 transition-colors ${
              selectedTab === 'series' 
                ? 'border-blue-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            Series
          </button>
          <button
            onClick={() => setSelectedTab('settings')}
            className={`px-4 py-3 border-b-2 transition-colors ${
              selectedTab === 'settings' 
                ? 'border-blue-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            Settings
          </button>
          <button
            onClick={() => setSelectedTab('logs')}
            className={`px-4 py-3 border-b-2 transition-colors ${
              selectedTab === 'logs' 
                ? 'border-blue-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            Download Logs
          </button>
        </div>
      </div>

      {/* Content */}
      <main className="p-6">
        {selectedTab === 'series' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold">Your Series</h2>
              <button
                onClick={() => {
                  setEditingSeries(null);
                  setShowAddSeries(true);
                }}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Series
              </button>
            </div>

            {config.series.length === 0 ? (
              <div className="bg-gray-800 rounded-lg p-12 text-center">
                <Download className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <h3 className="text-xl font-semibold mb-2">No series added yet</h3>
                <p className="text-gray-400 mb-6">Add your first series to start downloading episodes</p>
                <button
                  onClick={() => setShowAddSeries(true)}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  Add Your First Series
                </button>
              </div>
            ) : (
              <div className="grid gap-4">
                {config.series.map((series, index) => (
                  <div
                    key={index}
                    className={`bg-gray-800 rounded-lg p-6 border-2 transition-all ${
                      series.enabled ? 'border-blue-500/50' : 'border-transparent opacity-60'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <input
                            type="checkbox"
                            checked={series.enabled}
                            onChange={() => toggleSeries(index)}
                            className="w-5 h-5 rounded border-gray-600 bg-gray-700"
                          />
                          <h3 className="text-lg font-semibold">{series.name}</h3>
                        </div>
                        
                        <p className="text-sm text-gray-400 mb-3 font-mono">{series.url}</p>
                        
                        <div className="flex gap-4 text-sm">
                          <div>
                            <span className="text-gray-400">Include:</span>
                            <span className="ml-2 text-blue-400">
                              {series.include_patterns.length > 0 
                                ? series.include_patterns.join(', ') 
                                : 'All'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">Exclude:</span>
                            <span className="ml-2 text-red-400">
                              {series.exclude_patterns.length > 0 
                                ? series.exclude_patterns.join(', ') 
                                : 'None'}
                            </span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setEditingSeries(series);
                            setShowAddSeries(true);
                          }}
                          className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteSeries(index)}
                          className="p-2 bg-gray-700 hover:bg-red-600 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {selectedTab === 'settings' && (
          <div className="max-w-2xl">
            <h2 className="text-xl font-semibold mb-6">Settings</h2>
            
            <div className="bg-gray-800 rounded-lg p-6 space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">Download Path</label>
                <input
                  type="text"
                  value={config.download_path}
                  onChange={(e) => saveConfig({ ...config, download_path: e.target.value })}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Archive File</label>
                <input
                  type="text"
                  value={config.archive_file}
                  onChange={(e) => saveConfig({ ...config, archive_file: e.target.value })}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500"
                />
              </div>
              
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={config.debug}
                  onChange={(e) => saveConfig({ ...config, debug: e.target.checked })}
                  className="w-5 h-5 rounded border-gray-600 bg-gray-700"
                />
                <label className="text-sm font-medium">Debug Mode</label>
              </div>
            </div>
          </div>
        )}

        {selectedTab === 'logs' && (
          <div>
            <h2 className="text-xl font-semibold mb-6">Download Logs</h2>
            
            <div className="bg-gray-800 rounded-lg p-6 font-mono text-sm">
              {downloadLogs.length === 0 ? (
                <p className="text-gray-400">No downloads yet. Start a download to see logs here.</p>
              ) : (
                <div className="space-y-1">
                  {downloadLogs.map((log, index) => (
                    <div key={index} className="text-gray-300">{log}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Add/Edit Series Modal */}
      {showAddSeries && (
        <SeriesModal
          series={editingSeries}
          onSave={addOrUpdateSeries}
          onClose={() => {
            setShowAddSeries(false);
            setEditingSeries(null);
          }}
        />
      )}
    </div>
  );
}

// Series Modal Component
function SeriesModal({ 
  series, 
  onSave, 
  onClose 
}: { 
  series: Series | null;
  onSave: (series: Series) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(series?.name || '');
  const [url, setUrl] = useState(series?.url || '');
  const [includePatterns, setIncludePatterns] = useState(series?.include_patterns.join(', ') || '');
  const [excludePatterns, setExcludePatterns] = useState(series?.exclude_patterns.join(', ') || '');

  const handleSave = () => {
    if (!name || !url) return;
    
    onSave({
      name,
      url,
      enabled: series?.enabled ?? true,
      include_patterns: includePatterns.split(',').map(p => p.trim()).filter(p => p),
      exclude_patterns: excludePatterns.split(',').map(p => p.trim()).filter(p => p),
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-6">
          {series ? 'Edit Series' : 'Add New Series'}
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Series Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., ちょっとだけエスパー"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Series URL</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://tver.jp/series/..."
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">
              Include Patterns
              <span className="text-gray-400 text-xs ml-2">(comma-separated, leave empty to include all)</span>
            </label>
            <input
              type="text"
              value={includePatterns}
              onChange={(e) => setIncludePatterns(e.target.value)}
              placeholder="＃, #, 第"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Episodes must contain at least one of these patterns in the title
            </p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">
              Exclude Patterns
              <span className="text-gray-400 text-xs ml-2">(comma-separated)</span>
            </label>
            <input
              type="text"
              value={excludePatterns}
              onChange={(e) => setExcludePatterns(e.target.value)}
              placeholder="予告, ダイジェスト, 解説放送版, インタビュー"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Episodes containing these patterns will be skipped
            </p>
          </div>
        </div>
        
        <div className="flex gap-3 mt-6">
          <button
            onClick={handleSave}
            disabled={!name || !url}
            className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {series ? 'Update Series' : 'Add Series'}
          </button>
          <button
            onClick={onClose}
            className="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;