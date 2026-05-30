'use client';
import { Database, Folder, Search, Cloud, RefreshCcw, ChevronLeft, File, HardDrive, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';

const mockSystem = {
  'Firmware': [
     { name: 'esp32_galvo_v1.bin', size: '2.4 MB', date: '2023-10-24 10:20:00' },
     { name: 'motor_driver_patch.hex', size: '412 KB', date: '2023-10-23 09:15:00' }
  ],
  'AI Models': [
     { name: 'nav_pilot_v4.onnx', size: '14.2 MB', date: '2023-10-21 16:40:00' },
     { name: 'vision_classifier.tflite', size: '8.4 MB', date: '2023-10-20 11:10:00' }
  ],
  'Configs': [
     { name: 'pid_tuning.yaml', size: '1.2 KB', date: '2023-10-24 14:00:00' },
     { name: 'network_routes.json', size: '4.5 KB', date: '2023-10-22 08:00:00' }
  ],
  'Deployments': [
     { name: 'cluster_02_manifest.yaml', size: '12 KB', date: '2023-10-24 15:30:00' }
  ],
  'ROS Workspaces': [
     { name: 'neuros_ws.tar.gz', size: '145.2 MB', date: '2023-10-24 12:00:00' }
  ],
  'Logs': [
     { name: 'syslog-20231024.log', size: '24.1 MB', date: '2023-10-24 16:50:00' },
     { name: 'crash_dump_092.bin', size: '1.4 MB', date: '2023-10-23 18:22:00' }
  ]
};

export default function FilesView({ onClose }: { onClose?: () => void }) {
  const [activeDir, setActiveDir] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filesSys, setFilesSys] = useState(mockSystem);
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<{ dir: string; name: string } | null>(null);

  const handleSync = () => {
     setIsSyncing(true);
     setTimeout(() => setIsSyncing(false), 1500);
  };

  const deleteFile = (dir: string, name: string) => {
     setFilesSys(s => ({
         ...s,
         [dir]: s[dir as keyof typeof s].filter(f => f.name !== name)
     }));
     setPendingDelete(null);
  };

  return (
    <div className="h-full flex flex-col p-8 relative z-10 w-full max-w-6xl mx-auto bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <div className="flex items-center justify-between mb-8 shrink-0">
        <div>
          <h1 className="text-2xl font-light tracking-tight text-[var(--text-primary)] flex items-center gap-3 uppercase">
            Files
          </h1>
          <p className="text-[var(--text-secondary)] font-mono text-[10px] mt-2 tracking-widest flex items-center gap-2">
            INFRASTRUCTURE SYNC: <span className="text-[var(--accent)]">OPTIMAL</span>
            {isSyncing && <RefreshCcw className="w-3 h-3 text-[#00E5FF] animate-spin" />}
          </p>
        </div>
        <div className="flex items-center gap-4">
           {activeDir && (
               <button onClick={() => setActiveDir(null)} className="flex items-center gap-2 text-[10px] uppercase font-bold tracking-widest font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mr-4">
                 <ChevronLeft className="w-4 h-4" /> BACK TO ROOT
               </button>
           )}
           <div className="relative">
             <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
             <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="QUERY REGISTRY..." className="w-64 bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-md pl-9 pr-4 py-1.5 text-[11px] font-mono text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] outline-none transition-colors" />
           </div>
           <button onClick={handleSync} className={`p-2 rounded-md bg-[var(--panel-bg)] border border-[var(--panel-border)] transition-colors ${isSyncing ? 'text-[var(--accent)] border-[var(--accent)]' : 'text-[var(--text-secondary)] hover:text-[var(--accent)] hover:border-[var(--accent)]/30'}`}>
             <Cloud className={`w-4 h-4 ${isSyncing ? 'animate-pulse' : ''}`} />
           </button>
           {onClose && (
             <button onClick={onClose} className="p-2 rounded-md bg-[var(--panel-bg)] border border-[var(--panel-border)] hover:border-[#f44]/30 hover:text-[#f44] text-[var(--text-secondary)] transition-colors">
               <X className="w-4 h-4" />
             </button>
           )}
        </div>
      </div>

      <div className="flex-1 overflow-auto relative">
         <AnimatePresence mode="wait">
            {!activeDir ? (
                <motion.div 
                   key="root"
                   initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                   className="grid grid-cols-4 gap-4"
                >
                  {Object.entries(filesSys).filter(([dir]) => dir.toLowerCase().includes(search.toLowerCase())).map(([dir, files]) => (
                    <div key={dir} onClick={() => setActiveDir(dir)} className="p-4 rounded-lg border border-[var(--panel-border)] bg-[var(--panel-bg)] hover:border-[var(--accent)]/40 hover:bg-[#00E5FF]/5 transition-colors cursor-pointer group flex flex-col gap-3">
                      <div className="flex justify-between items-start">
                         <Folder className="w-6 h-6 text-[var(--text-secondary)] group-hover:text-[var(--accent)] transition-colors" />
                         <span className="text-[10px] font-mono text-[var(--text-secondary)]">{files.length} ITEMS</span>
                      </div>
                      <div>
                        <h3 className="font-mono text-[var(--text-primary)] text-xs uppercase tracking-wider">{dir}</h3>
                        <p className="text-[10px] text-[var(--text-secondary)] font-mono mt-1 tracking-widest">{isSyncing ? 'SYNCING...' : 'SYNCED'}</p>
                      </div>
                    </div>
                  ))}
                  {Object.keys(filesSys).filter(dir => dir.toLowerCase().includes(search.toLowerCase())).length === 0 && (
                      <div className="col-span-4 py-12 text-center text-[var(--text-secondary)] font-mono text-[11px] uppercase tracking-widest mt-8">
                          No matching directories found in registry.
                      </div>
                  )}
                </motion.div>
            ) : (
                <motion.div
                   key="dir"
                   initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
                   className="flex flex-col h-full"
                >
                   <div className="flex items-center gap-3 mb-6 bg-[var(--panel-bg)] border border-[var(--panel-border)] p-3 rounded-md shrink-0">
                      <Folder className="w-5 h-5 text-[var(--accent)]" />
                      <span className="font-mono text-[var(--text-primary)] tracking-widest uppercase">{activeDir}</span>
                      <div className="flex-1"/>
                      <span className="font-mono text-[10px] text-slate-400 tracking-widest">{filesSys[activeDir as keyof typeof filesSys].length} OBJECTS</span>
                   </div>

                   <div className="bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-md flex-1 overflow-hidden flex flex-col">
                      {/* Table Header */}
                      <div className="flex px-4 py-2 border-b border-[var(--panel-border)] bg-[var(--bg-secondary)] text-[10px] font-bold font-mono text-[var(--text-secondary)] tracking-widest uppercase shrink-0">
                         <div className="w-[40%]">Object Name</div>
                         <div className="w-[30%]">Last Modified</div>
                         <div className="w-[20%] text-right">Size</div>
                         <div className="w-[10%] text-right">Actions</div>
                      </div>
                      
                      {/* File List */}
                      <div className="flex-1 overflow-y-auto">
                         {filesSys[activeDir as keyof typeof filesSys].filter(f => f.name.toLowerCase().includes(search.toLowerCase())).map((file, i) => (
                             <div key={i} className="flex px-4 py-3 border-b border-[var(--panel-border)] hover:bg-[var(--bg-secondary)] transition-colors items-center font-mono text-[11px] group">
                                <div className="w-[40%] text-[var(--text-primary)] flex items-center gap-3">
                                   <File className="w-3.5 h-3.5 text-[var(--text-secondary)] group-hover:text-[var(--accent)] transition-colors shrink-0" />
                                   <span className="truncate">{file.name}</span>
                                </div>
                                <div className="w-[30%] text-[var(--text-secondary)]">{file.date}</div>
                                <div className="w-[20%] text-right text-[var(--text-secondary)]">{file.size}</div>
                                <div className="w-[10%] flex justify-end gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button className="text-[var(--text-secondary)] hover:text-[var(--accent)]"><HardDrive className="w-3.5 h-3.5"/></button>
                                    <button className="text-[var(--text-secondary)] hover:text-[#ff4e4e]" onClick={() => setPendingDelete({ dir: activeDir, name: file.name })}><Trash2 className="w-3.5 h-3.5"/></button>
                                </div>
                             </div>
                         ))}
                         {filesSys[activeDir as keyof typeof filesSys].filter(f => f.name.toLowerCase().includes(search.toLowerCase())).length === 0 && (
                            <div className="text-center text-[var(--text-secondary)] py-12 text-[11px] font-mono tracking-widest uppercase">No files match the query.</div>
                         )}
                      </div>
                   </div>
                </motion.div>
            )}
         </AnimatePresence>
      </div>
      <AnimatePresence>
        {pendingDelete && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <motion.div initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 10 }} className="w-full max-w-md rounded-md border border-[var(--panel-border)] bg-[var(--panel-bg)] p-5 shadow-2xl">
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">Delete File?</h3>
              <p className="mt-2 font-mono text-sm text-[var(--text-secondary)]">{pendingDelete.name}</p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">This action cannot be undone.</p>
              <div className="mt-5 flex justify-end gap-2">
                <button onClick={() => setPendingDelete(null)} className="rounded-md border border-[var(--panel-border)] px-4 py-2 text-sm text-[var(--text-secondary)]">Cancel</button>
                <button onClick={() => deleteFile(pendingDelete.dir, pendingDelete.name)} className="rounded-md border border-red-500 bg-red-500 px-4 py-2 text-sm font-semibold text-white">Delete</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
