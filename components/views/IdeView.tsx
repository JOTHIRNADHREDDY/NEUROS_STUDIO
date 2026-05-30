'use client';

import { XtermTerminal, type TerminalConnectionState, type XtermTerminalHandle } from '@/components/terminal/XtermTerminal';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useRef, useEffect } from 'react';
import {
  Folder, File, Terminal, Play, Save, ChevronRight, Cpu,
  Search, Bug, Bot, Activity, Check, ArrowRight, Settings, Maximize2, Minus, X, Menu,
  Library, Monitor, HardDrive, Download, ChevronDown, Trash2, Home, RefreshCcw
} from 'lucide-react';
import Editor from '@monaco-editor/react';
import PanelControls, { PanelDefinition } from '@/components/layout/PanelControls';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

type FileEntry = {
  id: string;
  name: string;
  path: string;
  content: string;
  savedContent: string;
  language: string;
  isDirty: boolean;
};

type ExplorerTarget = {
  kind: 'file' | 'folder';
  id?: string;
  label: string;
  path: string;
  dirty?: boolean;
};

type PendingAction = {
  mode: 'close' | 'delete';
  target: ExplorerTarget;
};

const idePanels: PanelDefinition[] = [
  { id: 'explorer', label: 'Explorer' },
  { id: 'editor', label: 'Editor' },
  { id: 'terminal', label: 'Terminal' },
  { id: 'ai', label: 'AI Copilot', shortLabel: 'AI' },
];

const defaultIdePanelVisibility = {
  explorer: true,
  editor: true,
  terminal: true,
  ai: true,
};

function getSavedIdeLayout() {
  if (typeof window === 'undefined') {
    return {};
  }

  const saved = window.localStorage.getItem('neuros-ide-panel-layout-v1');
  if (!saved) {
    return {};
  }

  try {
    return JSON.parse(saved) as {
      visibility?: Record<string, boolean>;
      explorerWidth?: number;
      aiPanelWidth?: number;
      terminalHeight?: number;
    };
  } catch {
    window.localStorage.removeItem('neuros-ide-panel-layout-v1');
    return {};
  }
}

const initialFiles: FileEntry[] = [
  {
    id: '1',
    name: 'main.cpp',
    path: 'src/main.cpp',
    content: `/*
 * NEUROS Studio - Galvo Servo Client
 * Hardware: DOIT ESP32 DEVKIT V1
 * Target: ROS2 Foxy / micro-ROS
 */

#include <Arduino.h>
#include <micro_ros_arduino.h>
#include "galvo_driver.h"
#include "config.h"

GalvoDriver g_laser;
rcl_node_t node;
rcl_publisher_t telemetry_pub;

void setup() {
  Serial.begin(115200);
  set_microros_transports();

  // Initialize galvo mirrors
  g_laser.init(PIN_X, PIN_Y);
  g_laser.calibrate();

  Serial.println("Galvo sub-system online.");
}

void loop() {
  // Stream vectors from ROS node
  if (g_laser.health_check() != OK) {
    Serial.println("ERR: Mirror thermal threshold.");
    delay(100);
    return;
  }
  delay(10);
}`,
    savedContent: `/*
 * NEUROS Studio - Galvo Servo Client
 * Hardware: DOIT ESP32 DEVKIT V1
 * Target: ROS2 Foxy / micro-ROS
 */

#include <Arduino.h>
#include <micro_ros_arduino.h>
#include "galvo_driver.h"
#include "config.h"

GalvoDriver g_laser;
rcl_node_t node;
rcl_publisher_t telemetry_pub;

void setup() {
  Serial.begin(115200);
  set_microros_transports();

  // Initialize galvo mirrors
  g_laser.init(PIN_X, PIN_Y);
  g_laser.calibrate();

  Serial.println("Galvo sub-system online.");
}

void loop() {
  // Stream vectors from ROS node
  if (g_laser.health_check() != OK) {
    Serial.println("ERR: Mirror thermal threshold.");
    delay(100);
    return;
  }
  delay(10);
}`,
    language: 'cpp',
    isDirty: false,
  },
  {
    id: '2',
    name: 'config.h',
    path: 'include/config.h',
    content: `#pragma once

#define PIN_X 12
#define PIN_Y 13
#define INVERT_X false
#define INVERT_Y true
`,
    savedContent: `#pragma once

#define PIN_X 12
#define PIN_Y 13
#define INVERT_X false
#define INVERT_Y true
`,
    language: 'cpp',
    isDirty: false,
  },
  {
    id: '3',
    name: 'CMakeLists.txt',
    path: 'CMakeLists.txt',
    content: `cmake_minimum_required(VERSION 3.16)
project(neuros_client)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)

# ... CMake configuration ...
`,
    savedContent: `cmake_minimum_required(VERSION 3.16)
project(neuros_client)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)

# ... CMake configuration ...
`,
    language: 'plaintext',
    isDirty: false,
  },
  {
    id: '4',
    name: 'kinematics.h',
    path: 'include/kinematics.h',
    content: `#pragma once

// Kinematics helpers for galvo control.
`,
    savedContent: `#pragma once

// Kinematics helpers for galvo control.
`,
    language: 'cpp',
    isDirty: false,
  },
  {
    id: '5',
    name: 'galvo_driver.cpp',
    path: 'src/galvo_driver.cpp',
    content: `#include "galvo_driver.h"

// Driver implementation placeholder.
`,
    savedContent: `#include "galvo_driver.h"

// Driver implementation placeholder.
`,
    language: 'cpp',
    isDirty: false,
  },
  {
    id: '6',
    name: 'platformio.ini',
    path: 'platformio.ini',
    content: `[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
`,
    savedContent: `[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
`,
    language: 'plaintext',
    isDirty: false,
  },
];

export default function IdeView({ onClose }: { onClose?: () => void }) {
  // Editor State
  const [files, setFiles] = useState<FileEntry[]>(initialFiles);
  const [openFiles, setOpenFiles] = useState(['1', '2', '3']);
  const [activeFileId, setActiveFileId] = useState('1');
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>(['1']);
  const [lastSelectedFileId, setLastSelectedFileId] = useState('1');
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [explorerMenu, setExplorerMenu] = useState<{ x: number; y: number; target: ExplorerTarget } | null>(null);
  
  // Output State
  const [terminalTab, setTerminalTab] = useState('Output');
  const [logs, setLogs] = useState<string[]>([
    "[SYSTEM] NEUROS Environment Ready",
    "Scanning for USB devices...",
    "Found ESP32 on COM7",
    "Opening serial connection at 115200 baud..."
  ]);
  const [isCompiling, setIsCompiling] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  // UI State
  const [activeSidebarItem, setActiveSidebarItem] = useState('explorer');
  const [panelVisibility, setPanelVisibility] = useState<Record<string, boolean>>(() => ({
    ...defaultIdePanelVisibility,
    ...(getSavedIdeLayout().visibility ?? {}),
  }));
  const [explorerWidth, setExplorerWidth] = useState(() => getSavedIdeLayout().explorerWidth ?? 260);
  const [aiPanelWidth, setAiPanelWidth] = useState(() => getSavedIdeLayout().aiPanelWidth ?? 340);
  const [terminalHeight, setTerminalHeight] = useState(() => getSavedIdeLayout().terminalHeight ?? 224);
  const [boardSelectOpen, setBoardSelectOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [aiPrompt, setAiPrompt] = useState("");
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [aiLogs, setAiLogs] = useState([
    { type: 'AI', text: "Detected repeated ping timeouts for the micro-ROS agent on COM7. This usually happens if the Agent node isn't running on your host machine or baud rates mismatch." },
  ]);

  const outputTerminalRef = useRef<XtermTerminalHandle>(null);
  const serialTerminalRef = useRef<XtermTerminalHandle>(null);
  const [outputTerminalStatus, setOutputTerminalStatus] = useState<TerminalConnectionState>('connecting');
  const [serialTerminalStatus, setSerialTerminalStatus] = useState<TerminalConnectionState>('connecting');

  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.localStorage.setItem('neuros-ide-panel-layout-v1', JSON.stringify({
      visibility: panelVisibility,
      explorerWidth,
      aiPanelWidth,
      terminalHeight,
    }));
  }, [panelVisibility, explorerWidth, aiPanelWidth, terminalHeight]);

  const togglePanel = (panelId: string) => {
    setPanelVisibility(prev => ({ ...prev, [panelId]: !(prev[panelId] ?? true) }));
  };

  const startResize = (
    axis: 'x' | 'y',
    current: number,
    setter: (value: number) => void,
    min: number,
    max: number,
    invert = false
  ) => (event: React.MouseEvent) => {
    event.preventDefault();
    const start = axis === 'x' ? event.clientX : event.clientY;
    const handleMove = (moveEvent: MouseEvent) => {
      const delta = (axis === 'x' ? moveEvent.clientX : moveEvent.clientY) - start;
      setter(Math.min(max, Math.max(min, current + (invert ? -delta : delta))));
    };
    const handleUp = () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
  };

  // Auto-scroll output panel
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [logs, terminalTab]);
  
  const aiOutputRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (aiOutputRef.current) {
      aiOutputRef.current.scrollTop = aiOutputRef.current.scrollHeight;
    }
  }, [aiLogs]);

  const addLog = (msg: string) => setLogs(l => [...l, msg]);

  const updateFileContent = (fileId: string, content: string) => {
    setFiles(prev => prev.map(file => file.id === fileId ? { ...file, content, isDirty: content !== file.savedContent } : file));
  };

  const saveFile = (fileId: string) => {
    setFiles(prev => prev.map(file => file.id === fileId ? { ...file, savedContent: file.content, isDirty: false } : file));
  };

  const discardFile = (fileId: string) => {
    setFiles(prev => prev.map(file => file.id === fileId ? { ...file, content: file.savedContent, isDirty: false } : file));
  };

  const closeFileImmediately = (fileId: string) => {
    setOpenFiles(prev => {
      const next = prev.filter(id => id !== fileId);
      if (activeFileId === fileId) {
        setActiveFileId(next[next.length - 1] ?? '1');
      }
      return next;
    });
  };

  const performDelete = async (target: ExplorerTarget) => {
    const encodedPath = target.path.split('/').map(segment => encodeURIComponent(segment)).join('/');
    const response = await fetch(`${API_BASE_URL}/api/${target.kind === 'folder' ? 'folders' : 'files'}/${encodedPath}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      throw new Error(errorPayload?.detail ?? errorPayload?.error ?? 'Delete request failed');
    }

    if (target.kind === 'folder') {
      const folderPrefix = `${target.path.replace(/\/$/, '')}/`;
      setFiles(prev => prev.filter(file => !file.path.startsWith(folderPrefix)));
      setOpenFiles(prev => prev.filter(fileId => {
        const file = files.find(entry => entry.id === fileId);
        return file ? !file.path.startsWith(folderPrefix) : true;
      }));
      if (files.find(entry => entry.id === activeFileId)?.path.startsWith(folderPrefix)) {
        const nextOpen = openFiles.filter(fileId => {
          const file = files.find(entry => entry.id === fileId);
          return file ? !file.path.startsWith(folderPrefix) : true;
        });
        setActiveFileId(nextOpen[nextOpen.length - 1] ?? '1');
      }
      return;
    }

    setFiles(prev => prev.filter(file => file.id !== target.id));
    setOpenFiles(prev => prev.filter(fileId => fileId !== target.id));
    if (activeFileId === target.id) {
      const nextOpen = openFiles.filter(fileId => fileId !== target.id);
      setActiveFileId(nextOpen[nextOpen.length - 1] ?? '1');
    }
    setSelectedFileIds(prev => prev.filter(fileId => fileId !== target.id));
  };

  const requestDelete = (target: ExplorerTarget) => {
    setPendingAction({ mode: 'delete', target });
  };

  const requestClose = (fileId: string) => {
    const file = files.find(entry => entry.id === fileId);
    if (!file) {
      return;
    }

    if (file.isDirty) {
      setPendingAction({ mode: 'close', target: { kind: 'file', id: fileId, label: file.name, path: file.path, dirty: true } });
      return;
    }

    closeFileImmediately(fileId);
  };

  const resolvePendingAction = async (choice: 'save' | 'discard' | 'delete' | 'cancel') => {
    if (!pendingAction || choice === 'cancel') {
      setPendingAction(null);
      return;
    }

    const { mode, target } = pendingAction;

    if (choice === 'save' && target.kind === 'file' && target.id) {
      saveFile(target.id);
    }

    if (choice === 'discard' && target.kind === 'file' && target.id) {
      discardFile(target.id);
    }

    if (mode === 'close' && target.kind === 'file' && target.id) {
      closeFileImmediately(target.id);
      setPendingAction(null);
      return;
    }

    if (mode === 'delete') {
      await performDelete(target);
    }

    setPendingAction(null);
  };

  const handleFileSelect = (fileId: string, event?: React.MouseEvent) => {
    if (event?.shiftKey) {
      const anchorIndex = files.findIndex(file => file.id === lastSelectedFileId);
      const currentIndex = files.findIndex(file => file.id === fileId);
      if (anchorIndex >= 0 && currentIndex >= 0) {
        const [start, end] = [anchorIndex, currentIndex].sort((a, b) => a - b);
        setSelectedFileIds(files.slice(start, end + 1).map(file => file.id));
      }
      setActiveFileId(fileId);
      return;
    }

    if (event?.metaKey || event?.ctrlKey) {
      setSelectedFileIds(prev => prev.includes(fileId) ? prev.filter(id => id !== fileId) : [...prev, fileId]);
      setActiveFileId(fileId);
      setLastSelectedFileId(fileId);
      return;
    }

    setSelectedFileIds([fileId]);
    setLastSelectedFileId(fileId);
    openFile(fileId);
  };

  const handleExplorerKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Delete' && activeSidebarItem === 'explorer' && selectedFileIds.length > 0) {
      event.preventDefault();
      const targetFile = files.find(file => file.id === selectedFileIds[0]);
      if (targetFile) {
        requestDelete({ kind: 'file', id: targetFile.id, label: targetFile.name, path: targetFile.path, dirty: targetFile.isDirty });
      }
    }
  };

  const filesInFolder = (folderPath: string) => files.filter(file => file.path.startsWith(`${folderPath}/`));
  const rootFiles = files.filter(file => !file.path.includes('/'));

  const moveSelectedFilesToFolder = (folderPath: string) => {
    if (selectedFileIds.length === 0) {
      return;
    }

    setFiles(prev => prev.map(file => {
      if (!selectedFileIds.includes(file.id)) {
        return file;
      }

      const nextPath = `${folderPath}/${file.name}`.replace(/^\/+/, '');
      return { ...file, path: nextPath };
    }));
  };

  const renderExplorerFile = (file: FileEntry) => (
    <TreeFile
      key={file.id}
      title={file.name}
      active={activeFileId === file.id}
      selected={selectedFileIds.includes(file.id)}
      onClick={(event) => handleFileSelect(file.id, event)}
      onDragStart={() => {
        if (!selectedFileIds.includes(file.id)) {
          setSelectedFileIds([file.id]);
          setLastSelectedFileId(file.id);
        }
      }}
      onContextMenu={(event) => setExplorerMenu({ x: event.clientX, y: event.clientY, target: { kind: 'file', id: file.id, label: file.name, path: file.path, dirty: file.isDirty } })}
    />
  );

  useEffect(() => {
    const handleWindowKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' || activeSidebarItem !== 'explorer' || selectedFileIds.length === 0) {
        return;
      }

      const targetFile = files.find(file => file.id === selectedFileIds[0]);
      if (targetFile) {
        event.preventDefault();
        requestDelete({ kind: 'file', id: targetFile.id, label: targetFile.name, path: targetFile.path, dirty: targetFile.isDirty });
      }
    };

    window.addEventListener('keydown', handleWindowKeyDown);
    return () => window.removeEventListener('keydown', handleWindowKeyDown);
  }, [activeSidebarItem, files, selectedFileIds]);

  const handleCompile = () => {
    if (isCompiling || isUploading) return;
    setTerminalTab('Output');
    setIsCompiling(true);
    addLog("[BUILD] Starting compilation...");
    
    let step = 0;
    const interval = setInterval(() => {
      step++;
      if (step === 1) addLog("Compiling core libraries...");
      if (step === 2) addLog("Compiling main.cpp...");
      if (step === 3) addLog("Linking ELF executable...");
      if (step === 4) {
        addLog("Generating binary...");
        setTimeout(() => {
          setIsCompiling(false);
          addLog("===============");
          addLog("[BUILD] SUCCESS: Sketch uses 262144 bytes (20%) of program storage space.");
        }, 500);
        clearInterval(interval);
      }
    }, 800);
  };

  const handleUpload = () => {
    if (isCompiling || isUploading) return;
    setTerminalTab('Output');
    setIsUploading(true);
    addLog("[UPLOAD] Initializing connection to COM7...");
    
    let step = 0;
    const interval = setInterval(() => {
      step++;
      if (step === 1) addLog("Hard resetting via RTS pin...");
      if (step === 2) addLog("Writing at 0x00010000... (25%)");
      if (step === 3) addLog("Writing at 0x00020000... (75%)");
      if (step === 4) {
        addLog("Writing at 0x00030000... (100%)");
        setTimeout(() => {
          setIsUploading(false);
          addLog("Leaving...");
          addLog("Hard resetting via RTS pin...");
          addLog("[UPLOAD] SUCCESS");
        }, 800);
        clearInterval(interval);
      }
    }, 600);
  };

  const sendAiPrompt = async (prompt: string) => {
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt || isAiLoading) {
      return;
    }

    setAiLogs(l => [...l, { type: 'USER', text: trimmedPrompt }]);
    setAiPrompt("");
    setIsAiLoading(true);

    try {
      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: trimmedPrompt,
          context: activeContent
            ? [
                `Active file: ${activeContent.name}`,
                `Language: ${activeContent.language}`,
                'Open file contents:',
                activeContent.content,
              ].join('\n')
            : '',
        }),
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.error ?? 'AI request failed');
      }

      const data = await response.json();
      const reply = typeof data.reply === 'string' && data.reply.trim()
        ? data.reply.trim()
        : 'The model returned an empty response.';

      setAiLogs(l => [...l, { type: 'AI', text: reply }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown AI request error';
      setAiLogs(l => [...l, { type: 'AI', text: `AI request failed: ${message}` }]);
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleAiSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      void sendAiPrompt(aiPrompt);
    }
  };

  const openFile = (id: string) => {
    if (!openFiles.includes(id)) {
      setOpenFiles([...openFiles, id]);
    }
    setActiveFileId(id);
  };

  const closeFile = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const newOpenFiles = openFiles.filter(f => f !== id);
    setOpenFiles(newOpenFiles);
    if (activeFileId === id) {
      setActiveFileId(newOpenFiles[newOpenFiles.length - 1] || "");
    }
  };

  const createFile = (folderPath = '') => {
    const name = `untitled-${files.length + 1}.cpp`;
    const path = folderPath ? `${folderPath}/${name}` : name;
    const nextFile: FileEntry = {
      id: `${Date.now()}`,
      name,
      path,
      content: '// New NEUROS source file\n',
      savedContent: '// New NEUROS source file\n',
      language: 'cpp',
      isDirty: false,
    };
    setFiles(prev => [...prev, nextFile]);
    setOpenFiles(prev => [...prev, nextFile.id]);
    setActiveFileId(nextFile.id);
    setSelectedFileIds([nextFile.id]);
  };

  const renameTarget = (target: ExplorerTarget) => {
    const nextName = window.prompt(`Rename ${target.label}`, target.label);
    if (!nextName || nextName === target.label) return;

    if (target.kind === 'folder') {
      const prefix = `${target.path}/`;
      const parent = target.path.includes('/') ? target.path.split('/').slice(0, -1).join('/') : '';
      const nextPath = parent ? `${parent}/${nextName}` : nextName;
      setFiles(prev => prev.map(file => file.path.startsWith(prefix) ? { ...file, path: file.path.replace(prefix, `${nextPath}/`) } : file));
      return;
    }

    setFiles(prev => prev.map(file => {
      if (file.id !== target.id) return file;
      const parent = file.path.includes('/') ? file.path.split('/').slice(0, -1).join('/') : '';
      return { ...file, name: nextName, path: parent ? `${parent}/${nextName}` : nextName, isDirty: true };
    }));
  };

  const duplicateFile = (target: ExplorerTarget) => {
    if (target.kind !== 'file' || !target.id) return;
    const source = files.find(file => file.id === target.id);
    if (!source) return;
    const extensionIndex = source.name.lastIndexOf('.');
    const base = extensionIndex > 0 ? source.name.slice(0, extensionIndex) : source.name;
    const ext = extensionIndex > 0 ? source.name.slice(extensionIndex) : '';
    const nextName = `${base}.copy${ext}`;
    const parent = source.path.includes('/') ? source.path.split('/').slice(0, -1).join('/') : '';
    const nextFile = {
      ...source,
      id: `${Date.now()}`,
      name: nextName,
      path: parent ? `${parent}/${nextName}` : nextName,
      isDirty: true,
    };
    setFiles(prev => [...prev, nextFile]);
    setOpenFiles(prev => [...prev, nextFile.id]);
    setActiveFileId(nextFile.id);
  };

  const copyPath = async (target: ExplorerTarget) => {
    await navigator.clipboard.writeText(target.path).catch(() => undefined);
  };

  const downloadTarget = (target: ExplorerTarget) => {
    if (target.kind !== 'file' || !target.id) return;
    const file = files.find(entry => entry.id === target.id);
    if (!file) return;
    const blob = new Blob([file.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = file.name;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const showProperties = (target: ExplorerTarget) => {
    const detail = target.kind === 'file'
      ? files.find(file => file.id === target.id)?.content.length ?? 0
      : filesInFolder(target.path).length;
    window.alert(`${target.label}\nPath: ${target.path}\nType: ${target.kind}\n${target.kind === 'file' ? `Size: ${detail} bytes` : `Contents: ${detail} files`}`);
  };

  const activeContent = files.find(f => f.id === activeFileId);
  const activeTerminalStatus = terminalTab === 'Output' ? outputTerminalStatus : serialTerminalStatus;
  const activeTerminalStatusClass = activeTerminalStatus === 'connected'
    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
    : activeTerminalStatus === 'connecting'
      ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
      : activeTerminalStatus === 'reconnecting'
        ? 'text-orange-400 bg-orange-500/10 border-orange-500/20'
        : 'text-red-400 bg-red-500/10 border-red-500/20';

  return (
    <div className="h-full min-h-0 flex flex-col z-10 relative font-sans selection:bg-[#00E5FF]/30 overflow-hidden bg-[#0A0D14] text-white" onClick={() => { setActiveMenu(null); setExplorerMenu(null); }}>
      {/* NATIVE DESKTOP TITLE BAR */}
      <div className="h-8 bg-[#111827] border-b border-[rgba(0,255,255,0.08)] flex flex-shrink-0 items-center justify-between px-3 z-50">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 bg-[#00E5FF] flex items-center justify-center rounded-md rotate-45 shadow-[0_0_8px_rgba(0,229,255,0.4)]">
            <span className="-rotate-45 font-black text-[#0A0D14] text-[8px]">N</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono font-bold tracking-widest text-white">ESP32_GALVOSERVO_CLIENT</span>
            <span className="text-white/50 text-[10px]">|</span>
            <span className="text-[10px] uppercase tracking-widest text-white/50">NEUROS Studio IDE</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 mr-2">
             <div className="w-1.5 h-1.5 rounded-full bg-[#00E5FF] animate-pulse shadow-[0_0_8px_rgba(0,229,255,0.8)]" />
             <span className="text-[9px] font-mono tracking-widest text-[#00E5FF]">CONNECTED</span>
          </div>
          {onClose && (
            <button onClick={onClose} className="flex items-center gap-2 px-3 py-1 bg-[#111827] hover:bg-[rgba(0,255,255,0.08)] border border-[rgba(0,255,255,0.08)] hover:border-[rgba(0,255,255,0.2)] text-white hover:text-[#00E5FF] transition-colors rounded-md ml-2">
              <Home className="w-3 h-3" />
              <span className="text-[10px] uppercase font-bold tracking-widest">Home</span>
            </button>
          )}
        </div>
      </div>

      {/* TOP MENU SYSTEM */}
      <div className="h-7 bg-[#111827] flex flex-shrink-0 items-center px-1 border-b border-[rgba(0,255,255,0.08)] relative z-40">
         {['File', 'Edit', 'Sketch', 'Tools', 'Help'].map((menu) => (
           <div key={menu} className="relative">
            <button 
              onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu === menu ? null : menu); }}
              className={`px-3 py-1 text-[11px] transition-colors rounded-md tracking-wide ${activeMenu === menu ? 'bg-[#111827] text-white' : 'text-white hover:bg-[#161B22] hover:text-white'}`}
            >
              {menu}
            </button>
            <AnimatePresence>
              {activeMenu === menu && (
                <motion.div 
                  initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.1 }}
                  className="absolute top-full left-0 mt-1 min-w-[240px] bg-[#111827] border border-[rgba(0,255,255,0.08)] rounded-md py-1 shadow-2xl flex flex-col z-50 text-white"
                  onClick={(e) => e.stopPropagation()}
                >
                  {menu === 'File' && (
                    <>
                      <MenuItem label="New Sketch" shortcut="Ctrl+N" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="New Cloud Sketch" shortcut="Alt+Ctrl+N" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Open..." shortcut="Ctrl+O" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Open Recent" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Sketchbook" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Examples" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Close" shortcut="Ctrl+W" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Save" shortcut="Ctrl+S" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Save As..." shortcut="Ctrl+Shift+S" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Preferences..." shortcut="Ctrl+Comma" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Advanced" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Quit" shortcut="Ctrl+Q" onClick={() => setActiveMenu(null)} />
                    </>
                  )}
                  {menu === 'Edit' && (
                    <>
                      <MenuItem label="Undo" shortcut="Ctrl+Z" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Redo" shortcut="Ctrl+Y" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Cut" shortcut="Ctrl+X" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Copy" shortcut="Ctrl+C" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Copy for Forum (Markdown)" shortcut="Ctrl+Shift+C" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Paste" shortcut="Ctrl+V" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Select All" shortcut="Ctrl+A" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Go to Line..." shortcut="Ctrl+L" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Comment/Uncomment" shortcut="Ctrl+/" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Increase Indent" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Decrease Indent" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Auto Format" shortcut="Ctrl+T" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Replace in Files" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Increase Font Size" shortcut="Ctrl+=" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Decrease Font Size" shortcut="Ctrl+-" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Find" shortcut="Ctrl+F" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Find Next" shortcut="Ctrl+G" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Find Previous" shortcut="Ctrl+Shift+G" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Use Selection for Find" shortcut="Ctrl+E" onClick={() => setActiveMenu(null)} />
                    </>
                  )}
                  {menu === 'Sketch' && (
                    <>
                      <MenuItem label="Verify/Compile" shortcut="Ctrl+R" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Upload" shortcut="Ctrl+U" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Configure and Upload" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Upload Using Programmer" shortcut="Ctrl+Shift+U" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Export Compiled Binary" shortcut="Alt+Ctrl+S" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Optimize for Debugging" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Show Sketch Folder" shortcut="Alt+Ctrl+K" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Include Library" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Add File..." onClick={() => setActiveMenu(null)} />
                    </>
                  )}
                  {menu === 'Tools' && (
                    <>
                      <MenuItem label="Auto Format" shortcut="Ctrl+T" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Archive Sketch" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Manage Libraries..." shortcut="Ctrl+Shift+I" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Serial Monitor" shortcut="Ctrl+Shift+M" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Serial Plotter" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Firmware Updater" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Upload SSL Root Certificates" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Board: &quot;ESP32 Dev Module&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Port: &quot;COM7&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Reload Board Data" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Get Board Info" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="CPU Frequency: &quot;240MHz (WiFi/BT)&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Core Debug Level: &quot;None&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Erase All Flash Before Sketch Upload: &quot;Disabled&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Events Run On: &quot;Core 1&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Flash Frequency: &quot;80MHz&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Flash Mode: &quot;QIO&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Flash Size: &quot;4MB (32Mb)&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="JTAG Adapter: &quot;Disabled&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Arduino Runs On: &quot;Core 1&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Partition Scheme: &quot;Default 4MB with spiffs (1.2MB APP/1.5MB SPIFFS)&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="PSRAM: &quot;Disabled&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Upload Speed: &quot;921600&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Zigbee Mode: &quot;Disabled&quot;" hasSubmenu onClick={() => setActiveMenu(null)} />
                    </>
                  )}
                  {menu === 'Help' && (
                    <>
                      <MenuItem label="Getting Started" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Environment" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Troubleshooting" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Reference" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="Find in Reference" shortcut="Ctrl+Shift+F" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Frequently Asked Questions" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Visit Studio IDE Website" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Privacy Policy" onClick={() => setActiveMenu(null)} />
                      <MenuItem label="Check for Studio IDE Updates" onClick={() => setActiveMenu(null)} />
                      <MenuDivider />
                      <MenuItem label="About Studio IDE" onClick={() => setActiveMenu(null)} />
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
           </div>
         ))}
      </div>

      {/* TOP ACTION TOOLBAR (Arduino Style) */}
      <div className="h-12 bg-[#111827] border-b border-[rgba(0,255,255,0.08)] flex flex-shrink-0 items-center px-3 gap-3 relative overflow-hidden z-30">
        <div className="absolute top-0 right-0 h-px w-32 bg-gradient-to-l from-[#00E5FF]/100 to-transparent animate-[pulse_3s_ease-in-out_infinite]" />
        
        <button 
          title="Verify / Compile"
          onClick={handleCompile}
          disabled={isCompiling || isUploading}
          className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all group relative overflow-hidden ${isCompiling ? 'bg-[#00E5FF]/20 border-[#00E5FF] text-[#00E5FF] scale-95' : 'bg-[#111827] border-[rgba(0,255,255,0.08)] text-white hover:text-[#00E5FF] hover:border-[#00E5FF] hover:shadow-[0_0_12px_rgba(0,242,255,0.2)] hover:scale-105'}`}
        >
          {isCompiling && <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }} className="absolute inset-[2px] rounded-full border border-t-[#00E5FF] border-r-transparent border-b-transparent border-l-transparent" />}
          <Check className="w-4 h-4 relative z-10" />
        </button>
        <button 
          title="Upload to Device"
          onClick={handleUpload}
          disabled={isCompiling || isUploading}
          className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all relative overflow-hidden group ${isUploading ? 'bg-[#00E5FF] border-[#00E5FF] text-white shadow-[0_0_20px_rgba(0,242,255,0.8)] scale-95' : 'bg-[#00E5FF]/10 border-[#00E5FF]/30 text-[#00E5FF] hover:bg-[#00E5FF] hover:text-white hover:shadow-[0_0_15px_rgba(0,242,255,0.6)] hover:scale-105'}`}
        >
          {isUploading && <motion.div animate={{ y: [-20, 20] }} transition={{ repeat: Infinity, duration: 1 }} className="absolute inset-0 bg-[#111827]/40" />}
          {!isUploading && <div className="absolute inset-0 bg-[#111827]/20 translate-y-full group-hover:translate-y-0 transition-transform" />}
          <ArrowRight className={`w-4 h-4 relative z-10 ${isUploading ? '-rotate-90' : ''} transition-transform`} />
        </button>
        <button 
          title="Debug"
          onClick={() => { setActiveSidebarItem('debug'); setTerminalTab('Debug Console'); }}
          className="w-8 h-8 rounded-full flex items-center justify-center bg-[#111827] border border-[rgba(0,255,255,0.08)] text-white hover:text-[#ffae00] hover:border-[#ffae00] hover:shadow-[0_0_12px_rgba(255,174,0,0.2)] transition-all hover:scale-105"
        >
          <Bug className="w-4 h-4" />
        </button>
        <button 
          title="Stop"
          className="w-8 h-8 rounded-full flex items-center justify-center bg-[#111827] border border-[rgba(0,255,255,0.08)] text-white hover:text-[#ff4e4e] hover:border-[#ff4e4e] transition-all hover:scale-105"
        >
          <div className="w-2.5 h-2.5 bg-current rounded-md" />
        </button>

        <div className="flex-1" />

        {/* Board Selection */}
        <div className="relative flex items-center gap-2">
           <button 
              onClick={(e) => { e.stopPropagation(); setBoardSelectOpen(!boardSelectOpen); }}
              className="flex items-center gap-2 bg-[#111827] border border-[rgba(0,255,255,0.08)] hover:border-[#00E5FF] hover:text-[#00E5FF] transition-colors rounded-md px-4 py-1.5 text-[10px] font-mono group relative"
           >
             <Cpu className="w-3.5 h-3.5 text-white/50 group-hover:text-[#00E5FF]" />
             <span>DOIT ESP32 DEVKIT V1</span>
             <ChevronDown className="w-3 h-3 text-white/50 group-hover:text-[#00E5FF]" />
           </button>
           
           <AnimatePresence>
             {boardSelectOpen && (
                <motion.div 
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 5 }}
                  transition={{ duration: 0.1 }}
                  className="absolute top-full right-0 mt-2 w-96 bg-[#111827] border border-[rgba(0,255,255,0.08)] rounded-md shadow-2xl z-50 p-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center bg-[#111827] border border-[rgba(0,255,255,0.08)] rounded-md px-2 py-1 mb-2">
                    <Search className="w-3 h-3 text-white/50 mr-2" />
                    <input type="text" placeholder="Search boards..." className="bg-transparent text-[11px] font-mono text-white outline-none w-full" />
                  </div>
                  <div className="text-[9px] uppercase tracking-widest text-white/50 mb-1 px-1 font-bold">Detected Boards on Ports</div>
                  <div className="space-y-1">
                    <button className="w-full flex items-center justify-between text-left px-2 py-1.5 hover:bg-[#00E5FF]/10 border border-transparent hover:border-[#00E5FF]/30 rounded-md group transition-all" onClick={() => setBoardSelectOpen(false)}>
                      <div className="flex items-center gap-2">
                         <div className="w-1.5 h-1.5 rounded-full bg-[#00E5FF] animate-pulse" />
                         <span className="text-[11px] font-mono text-white">DOIT ESP32 DEVKIT V1</span>
                      </div>
                      <span className="text-[10px] font-mono text-[#00E5FF]">COM7</span>
                    </button>
                    <button className="w-full flex items-center justify-between text-left px-2 py-1.5 hover:bg-[#111827] border border-transparent rounded-md text-white/50 transition-all">
                      <div className="flex items-center gap-2">
                         <div className="w-1.5 h-1.5 rounded-full bg-[#5a5a5d]" />
                         <span className="text-[11px] font-mono">Arduino Uno WiFi Rev2</span>
                      </div>
                      <span className="text-[10px] font-mono">Disconnected</span>
                    </button>
                  </div>
                </motion.div>
             )}
           </AnimatePresence>
        </div>

        {/* Port Selector */}
        <div className="flex items-center bg-[#111827] border border-[rgba(0,255,255,0.08)] rounded-md pr-1 group hover:border-[#00E5FF]/50 transition-colors cursor-pointer" onClick={() => setTerminalTab('Serial Monitor')}>
           <button className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-mono tracking-widest text-white group-hover:text-white transition-colors border-r border-[rgba(0,255,255,0.08)]">
              <Monitor className="w-3.5 h-3.5 text-white/50 group-hover:text-[#00E5FF]" />
              <span className="hidden sm:inline">COM7 / </span>dev/ttyUSB0
           </button>
           <button className="px-2 py-1.5 text-white/50 group-hover:text-[#00E5FF] transition-colors">
              <ChevronRight className="w-3 h-3 rotate-90" />
           </button>
        </div>
      </div>

      <div className="border-b border-[rgba(0,255,255,0.08)] bg-[#111827] px-3 py-2">
        <PanelControls panels={idePanels} visible={panelVisibility} onToggle={togglePanel} />
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* LEFT ACTIVITY SIDEBAR */}
        {panelVisibility.explorer && <div className="w-12 bg-[#111827] border-r border-[rgba(0,255,255,0.08)] flex flex-col items-center py-3 gap-2 z-20 shrink-0 rounded-lg">
          {[
            { id: 'explorer', icon: Folder, label: 'Explorer' },
            { id: 'boards', icon: Cpu, label: 'Boards Manager' },
            { id: 'libraries', icon: Library, label: 'Library Manager' },
            { id: 'debug', icon: Bug, label: 'Run and Debug' },
            { id: 'search', icon: Search, label: 'Search' },
            { id: 'serial', icon: Terminal, label: 'Serial Devices' },
          ].map(item => (
            <button
              key={item.id}
              onClick={() => setActiveSidebarItem(item.id)}
              className={`relative p-2 rounded-md transition-colors group flex items-center justify-center w-10 h-10 ${activeSidebarItem === item.id ? 'text-white' : 'text-white/50 hover:text-white'}`}
              title={item.label}
            >
              <item.icon className="w-5 h-5" strokeWidth={activeSidebarItem === item.id ? 2 : 1.5} />
              {activeSidebarItem === item.id && (
                <motion.div layoutId="sidebar-active" className="absolute left-[-2px] top-1/4 bottom-1/4 w-[2px] bg-[#00E5FF] shadow-[0_0_8px_rgba(0,242,255,0.6)]" />
              )}
            </button>
          ))}
          <div className="flex-1" />
          <button
            onClick={() => togglePanel('ai')}
            className={`relative p-2 rounded-md transition-colors group flex items-center justify-center w-10 h-10 ${panelVisibility.ai ? 'text-[#00E5FF]' : 'text-white/50 hover:text-[#00E5FF]'}`}
            title="Toggle AI Co-Pilot"
          >
            <Bot className="w-5 h-5" strokeWidth={panelVisibility.ai ? 2 : 1.5} />
            {panelVisibility.ai && (
               <div className="absolute left-[-2px] top-1/4 bottom-1/4 w-[2px] bg-[#00E5FF] shadow-[0_0_8px_rgba(0,242,255,0.6)]" />
            )}
          </button>
          <button className="relative p-2 rounded-md transition-colors group flex items-center justify-center w-10 h-10 text-white/50 hover:text-white" title="ROS Integration">
            <Activity className="w-5 h-5" strokeWidth={1.5} />
          </button>
          <button className="relative p-2 rounded-md transition-colors group flex items-center justify-center w-10 h-10 text-white/50 hover:text-white" title="Settings">
            <Settings className="w-5 h-5" strokeWidth={1.5} />
          </button>
        </div>}

        {/* LEFT DYNAMIC TOOL PANEL */}
        {panelVisibility.explorer && <div className="bg-[#111827] border-r border-[rgba(0,255,255,0.08)] flex flex-col flex-shrink-0 z-10 relative rounded-lg" style={{ width: explorerWidth }}>
          
          <div className="px-4 py-2 bg-[#111827] text-[10px] font-mono font-bold tracking-widest text-white uppercase flex justify-between items-center border-b border-[rgba(0,255,255,0.08)] h-8 shrink-0">
            {activeSidebarItem}
          </div>
          
          <div className="flex-1 overflow-y-auto p-2" tabIndex={0} onKeyDown={handleExplorerKeyDown} onClick={() => setExplorerMenu(null)}>
            {activeSidebarItem === 'explorer' && (
              <div className="space-y-0.5">
                <TreeFolder title="ESP32_GALVOSERVO_CLIENT" defaultExpanded onContextMenu={(event) => setExplorerMenu({ x: event.clientX, y: event.clientY, target: { kind: 'folder', label: 'ESP32_GALVOSERVO_CLIENT', path: '.' } })}>
                  <TreeFolder title=".vscode" onDrop={() => moveSelectedFilesToFolder('.vscode')} />
                  <TreeFolder title="include" defaultExpanded onDrop={() => moveSelectedFilesToFolder('include')} onContextMenu={(event) => setExplorerMenu({ x: event.clientX, y: event.clientY, target: { kind: 'folder', label: 'include', path: 'include' } })}>
                     {filesInFolder('include').map(renderExplorerFile)}
                  </TreeFolder>
                  <TreeFolder title="src" defaultExpanded onDrop={() => moveSelectedFilesToFolder('src')} onContextMenu={(event) => setExplorerMenu({ x: event.clientX, y: event.clientY, target: { kind: 'folder', label: 'src', path: 'src' } })}>
                    {filesInFolder('src').map(renderExplorerFile)}
                  </TreeFolder>
                  {rootFiles.map(renderExplorerFile)}
                </TreeFolder>
              </div>
            )}
            {activeSidebarItem === 'boards' && (
                <div className="space-y-3">
                    <div className="bg-[#111827] border border-[rgba(0,255,255,0.08)] rounded-md p-2 text-[11px]">
                        <input type="text" placeholder="Filter boards..." className="bg-transparent w-full text-white outline-none"/>
                    </div>
                    <div className="space-y-2">
                        <div className="p-2 border border-[#00E5FF]/30 bg-[#00E5FF]/5 rounded-md">
                            <h3 className="text-white text-[11px] font-bold">esp32 by Espressif Systems</h3>
                            <p className="text-white/50 text-[10px] mt-1">Installed: 2.0.11</p>
                            <button className="mt-2 text-[10px] bg-[#111827] border border-[rgba(0,255,255,0.08)] px-2 py-1 rounded-md w-full hover:border-[#00E5FF] hover:text-[#00E5FF] transition-colors text-white">UPDATE TO 2.0.14</button>
                        </div>
                         <div className="p-2 border border-[rgba(0,255,255,0.08)] bg-[#111827] rounded-md">
                            <h3 className="text-white text-[11px] font-bold">Arduino AVR Boards</h3>
                            <p className="text-white/50 text-[10px] mt-1">Installed: 1.8.6</p>
                            <button className="mt-2 text-[10px] bg-[#111827] border border-[rgba(0,255,255,0.08)] px-2 py-1 rounded-md text-white/50 w-full hover:border-white hover:text-white transition-colors">REMOVE</button>
                        </div>
                    </div>
                </div>
            )}
            {activeSidebarItem === 'debug' && (
                <div className="space-y-4 font-mono text-[11px]">
                     <div className="flex gap-2 mb-4">
                        <button className="flex-1 bg-[#111827] border border-[rgba(0,255,255,0.08)] hover:border-[#00ff00] text-[#00ff00] py-1 rounded-md transition-colors flex items-center justify-center gap-1">
                            <Play className="w-3 h-3" /> Start
                        </button>
                     </div>
                     <div>
                        <div className="text-white/50 tracking-widest uppercase text-[9px] font-bold mb-1 px-1">Variables</div>
                        <div className="border border-[rgba(0,255,255,0.08)] bg-[#111827] p-2 rounded-md space-y-1">
                            <div className="flex justify-between hover:bg-[#161B22] px-1 cursor-pointer"><span className="text-purple-600">g_laser.x</span> <span className="text-green-600">1024</span></div>
                            <div className="flex justify-between hover:bg-[#161B22] px-1 cursor-pointer"><span className="text-purple-600">g_laser.y</span> <span className="text-green-600">2048</span></div>
                            <div className="flex justify-between hover:bg-[#161B22] px-1 cursor-pointer"><span className="text-purple-600">status</span> <span className="text-blue-600">OK (0)</span></div>
                        </div>
                     </div>
                     <div>
                        <div className="text-white/50 tracking-widest uppercase text-[9px] font-bold mb-1 px-1">Call Stack</div>
                        <div className="border border-[rgba(0,255,255,0.08)] bg-[#111827] p-2 rounded-md space-y-1">
                            <div className="hover:bg-[#161B22] px-1 cursor-pointer text-yellow-600">loop() <span className="text-white/50">main.cpp:25</span></div>
                            <div className="hover:bg-[#161B22] px-1 cursor-pointer text-yellow-600">main() <span className="text-white/50">sys.cpp:142</span></div>
                        </div>
                     </div>
                </div>
            )}
            {!['explorer', 'boards', 'debug'].includes(activeSidebarItem) && (
              <div className="h-full flex items-center justify-center opacity-30 text-[10px] font-mono tracking-widest text-center px-4">
                [ {activeSidebarItem.toUpperCase()} MODULE ]<br/>STANDING BY
              </div>
            )}
          </div>
        </div>}
        {panelVisibility.explorer && <div className="resizer-x" onMouseDown={startResize('x', explorerWidth, setExplorerWidth, 180, 420)} />}

        {/* CENTER CODE EDITOR & BOTTOM OUTPUT */}
        {panelVisibility.editor && <div className="flex-1 flex flex-col bg-[#111827] relative flex-shrink min-w-0">
          
          {/* Editor Tabs */}
          <div className="flex h-9 bg-[#111827] border-b border-[rgba(0,255,255,0.08)] shrink-0 overflow-x-auto custom-scrollbar">
             {openFiles.map(fileId => {
                 const file = files.find(f => f.id === fileId);
                 if (!file) return null;
                 const isActive = activeFileId === fileId;
                 return (
                    <div 
                        key={fileId}
                        onClick={() => setActiveFileId(fileId)}
                        className={`flex items-center px-3 gap-2 border-r border-[rgba(0,255,255,0.08)] border-t-2 cursor-pointer min-w-[140px] group transition-colors ${isActive ? 'bg-[#111827] border-t-[#00E5FF]' : 'bg-[#111827] hover:bg-[#161B22] border-t-transparent'}`}
                    >
                        <File className={`w-3.5 h-3.5 ${isActive ? 'text-[#00E5FF]' : 'text-white/50'}`} />
                  <span className={`text-[11px] font-mono ${isActive ? 'text-white' : 'text-white/50 group-hover:text-white'} ${file.isDirty ? 'italic' : ''}`}>{file.name}</span>
                  {file.isDirty && <span className="text-[9px] text-[#00E5FF] uppercase tracking-widest">*</span>}
                        <div className="flex-1" />
                        <X 
                    onClick={(e) => { e.stopPropagation(); requestClose(fileId); }}
                            className={`w-3 h-3 hover:text-white transition-all rounded-md hover:bg-[rgba(0,255,255,0.08)] p-[1px] ${isActive ? 'text-white/50' : 'opacity-0 group-hover:opacity-100 text-white/50'}`} 
                        />
                    </div>
                 )
             })}
            <div className="flex-1 bg-[#111827]"></div>
          </div>

          {/* Monaco Style Breadcrumbs */}
           {activeContent && (
             <div className="h-6 bg-[#111827] border-b border-[rgba(0,255,255,0.08)] flex items-center px-3 text-[10px] font-mono text-white/50 gap-1 shrink-0 w-full z-10 transition-all">
                <span className="hover:text-white cursor-pointer transition-colors">ESP32_GALVOSERVO_CLIENT</span>
                <ChevronRight className="w-3 h-3" />
                <span className="hover:text-white cursor-pointer transition-colors">src</span>
                <ChevronRight className="w-3 h-3" />
                <span className="text-white">{activeContent.name}</span>
             </div>
           )}

          {/* Editor Area */}
          <div className="flex-1 overflow-auto bg-[#111827] flex relative min-h-[100px]">
             {activeContent ? (
                  <Editor
                      height="100%"
                      defaultLanguage={activeContent.language}
                      language={activeContent.language}
                      value={activeContent.content}
                      theme="vs-dark"
                      onChange={(value) => {
                          updateFileContent(activeFileId, value || "");
                      }}
                      options={{
                          minimap: { enabled: true, scale: 0.75, renderCharacters: false },
                          fontSize: 13,
                          fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
                          lineHeight: 22,
                          padding: { top: 16 },
                          scrollBeyondLastLine: false,
                          smoothScrolling: true,
                          cursorBlinking: "smooth",
                          cursorSmoothCaretAnimation: "on",
                          formatOnPaste: true,
                          renderWhitespace: "selection",
                          overviewRulerBorder: false,
                          hideCursorInOverviewRuler: true
                      }}
                  />
             ) : (
                 <div className="flex-1 flex items-center justify-center text-white/50 font-mono text-sm opacity-50">
                     No file open. Select a file from the Explorer.
                 </div>
             )}
          </div>

          {/* BOTTOM OUTPUT PANEL */}
          {panelVisibility.terminal && <div className="min-h-[96px] bg-[#111827] border-t border-[rgba(0,255,255,0.08)] flex flex-col shrink-0 relative shadow-[0_-10px_20px_rgba(0,0,0,0.4)] rounded-t-xl" style={{ height: terminalHeight }}>
             <div className="absolute top-0 left-0 right-0 h-1 cursor-row-resize bg-transparent hover:bg-[#00E5FF]/30 transition-colors z-20 -translate-y-1/2" onMouseDown={startResize('y', terminalHeight, setTerminalHeight, 96, 420, true)} />
             <div className="h-8 border-b border-[rgba(0,255,255,0.08)] flex items-center px-1 bg-[#111827]">
               {['Output', 'Serial Monitor', 'Debug Console'].map((tab) => (
                 <button 
                    key={tab} 
                    onClick={() => setTerminalTab(tab)}
                    className={`px-4 h-full text-[10px] font-mono tracking-widest uppercase flex items-center transition-colors border-b-[2px] outline-none ${terminalTab === tab ? 'border-[#00E5FF] text-white' : 'border-transparent text-white/50 hover:text-white'}`}
                 >
                   {tab}
                 </button>
               ))}
               <div className="flex-1" />
                 <div className="flex items-center gap-3 px-3 border-l border-[rgba(0,255,255,0.08)] text-white/50 text-[10px] font-mono h-full">
                  <span className={`px-2 py-0.5 rounded-full border inline-flex items-center gap-1.5 capitalize ${activeTerminalStatusClass}`}>
                    <span className="text-[8px] leading-none">●</span>
                    {activeTerminalStatus}
                  </span>
                  <span className="hover:text-white cursor-pointer transition-colors flex items-center">115200 baud <ChevronDown className="ml-1 w-3 h-3"/></span>
                  <button title="Reconnect" className="hover:text-white transition-colors p-1 rounded-md hover:bg-[rgba(0,255,255,0.08)]" onClick={() => (terminalTab === 'Output' ? outputTerminalRef.current : serialTerminalRef.current)?.reconnect()}><RefreshCcw className="w-3.5 h-3.5" /></button>
                  <button title="Clear Terminal" className="hover:text-white transition-colors p-1 rounded-md hover:bg-[rgba(0,255,255,0.08)]" onClick={() => (terminalTab === 'Output' ? outputTerminalRef.current : serialTerminalRef.current)?.clear()}><Trash2 className="w-3.5 h-3.5" /></button>
                  <button title="Copy Selection" className="hover:text-white transition-colors p-1 rounded-md hover:bg-[rgba(0,255,255,0.08)]" onClick={() => void (terminalTab === 'Output' ? outputTerminalRef.current : serialTerminalRef.current)?.copySelection()}><Download className="w-3.5 h-3.5" /></button>
               </div>
             </div>
             
             {/* Scrolling Container */}
               <div className="flex-1 overflow-hidden bg-black p-2 font-mono text-[11px] leading-[1.6] relative">
                 {terminalTab === 'Output' && (
                   <XtermTerminal ref={outputTerminalRef} wsUrl="ws://localhost:8000/api/ide/pty" onStatusChange={setOutputTerminalStatus} forceTheme="dark" />
                 )}
                 {terminalTab === 'Serial Monitor' && (
                   <XtermTerminal ref={serialTerminalRef} wsUrl="ws://localhost:8000/api/ide/serial_pty" onStatusChange={setSerialTerminalStatus} forceTheme="dark" />
                 )}
                 {terminalTab === 'Debug Console' && (
                     <div className="text-white/50 italic">Debug console idle. Connect debugger to view variables and stack traces.</div>
                 )}
             </div>
          </div>}
        </div>}

        {panelVisibility.ai && <div className="resizer-x" onMouseDown={startResize('x', aiPanelWidth, setAiPanelWidth, 260, 520, true)} />}

        {/* RIGHT AI ASSISTANT PANEL */}
        <AnimatePresence>
          {panelVisibility.ai && (
            <motion.div 
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: aiPanelWidth, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
              className="border-l border-[rgba(0,255,255,0.08)] bg-[#111827] flex flex-col z-20 shrink-0 overflow-hidden shadow-[-10px_0_30px_rgba(0,0,0,0.5)] relative"
            >
              <div className="absolute inset-0 bg-[#00E5FF]/[0.02] pointer-events-none" />
              <div className="h-8 border-b border-[rgba(0,255,255,0.08)] flex items-center justify-between px-3 shrink-0 relative bg-[#111827]">
                <div className="flex items-center gap-2">
                  <Bot className="w-3.5 h-3.5 text-[#00E5FF]" />
                  <span className="text-[10px] font-mono tracking-widest font-bold uppercase text-white">AI Co-Pilot</span>
                </div>
                <div>
                  <button className="text-white/50 hover:text-white transition-colors p-1 rounded hover:bg-[rgba(0,255,255,0.08)]" onClick={() => togglePanel('ai')}>
                     <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div ref={aiOutputRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 font-mono relative scroll-smooth custom-scrollbar">
                {/* AI Background Pulse */}
                <div className="absolute top-10 right-10 w-32 h-32 bg-[#00E5FF] rounded-full blur-[80px] opacity-[0.05] pointer-events-none" />

                {aiLogs.map((log, i) => (
                     <div key={i} className={`flex flex-col z-10 ${log.type === 'USER' ? 'items-end' : 'items-start'}`}>
                         {log.type === 'AI' && (
                             <div className="flex items-center gap-2 mb-1.5 ml-1">
                                <Bot className="w-3 h-3 text-[#00E5FF]" />
                                <span className="text-[9px] text-[#00E5FF] font-bold uppercase tracking-widest">System</span>
                             </div>
                         )}
                         <div className={`p-2.5 rounded-md text-[11px] leading-relaxed relative max-w-[95%] shadow-sm ${log.type === 'USER' ? 'bg-[rgba(0,255,255,0.08)] text-white border border-[#00E5FF]/30' : 'bg-[#111827]/90 border border-[rgba(0,255,255,0.08)] text-white backdrop-blur-sm'}`}>
                             {log.type === 'AI' && <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#00E5FF] rounded-l-sm" />}
                             {log.text}
                         </div>
                     </div>
                ))}
              </div>

              {/* Chat Input */}
              <div className="p-3 border-t border-[rgba(0,255,255,0.08)] bg-[#111827] shrink-0 z-10 shadow-[0_-5px_15px_rgba(0,0,0,0.3)]">
                <div className="bg-[#111827] border border-[rgba(0,255,255,0.08)] flex items-center px-3 py-2.5 rounded-md focus-within:border-[#00E5FF]/60 transition-all shadow-inner relative overflow-hidden group">
                  <div className="absolute bottom-0 left-0 h-px w-0 bg-[#00E5FF] transition-all duration-500 group-focus-within:w-full" />
                  <input 
                    type="text" 
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    onKeyDown={handleAiSubmit}
                    placeholder="Ask AI to explain, debug, or generate code..." 
                    disabled={isAiLoading}
                    className="bg-transparent flex-1 outline-none text-[11px] font-mono text-white placeholder:text-white/50 disabled:cursor-not-allowed disabled:opacity-60" 
                  />
                  <Bot
                    className={`w-4 h-4 shrink-0 transition-colors ${aiPrompt && !isAiLoading ? 'text-[#00E5FF] cursor-pointer' : 'text-white/50'}`}
                    onClick={() => void sendAiPrompt(aiPrompt)}
                  />
                </div>
                <div className="flex gap-2 mt-2">
                    <button onClick={() => setAiPrompt("Optimize the setup() logic")} className="text-[9px] font-mono text-white/50 hover:text-[#00E5FF] border border-[rgba(0,255,255,0.08)] hover:border-[#00E5FF]/30 bg-[#111827] px-2 py-1 rounded-md transition-all flex-1">Optimize Mode</button>
                    <button onClick={() => setAiPrompt("Explain this code")} className="text-[9px] font-mono text-white/50 hover:text-[#00E5FF] border border-[rgba(0,255,255,0.08)] hover:border-[#00E5FF]/30 bg-[#111827] px-2 py-1 rounded-md transition-all flex-1">Explain File</button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {explorerMenu && (
            <motion.div
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.12 }}
              className="fixed z-[80] min-w-56 rounded-lg border border-[rgba(0,255,255,0.12)] bg-[#111827] p-1 shadow-2xl text-[11px] font-mono text-white"
              style={{ left: explorerMenu.x, top: explorerMenu.y }}
              onClick={(event) => event.stopPropagation()}
              onContextMenu={(event) => event.preventDefault()}
            >
              {explorerMenu.target.kind === 'file' ? (
                <>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { if (explorerMenu.target.id) openFile(explorerMenu.target.id); setExplorerMenu(null); }}>Open</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { if (explorerMenu.target.id) openFile(explorerMenu.target.id); setExplorerMenu(null); }}>Edit</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { renameTarget(explorerMenu.target); setExplorerMenu(null); }}>Rename</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { duplicateFile(explorerMenu.target); setExplorerMenu(null); }}>Duplicate</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5 text-red-300" onClick={() => { requestDelete(explorerMenu.target); setExplorerMenu(null); }}>Delete</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { void copyPath(explorerMenu.target); setExplorerMenu(null); }}>Copy Path</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { downloadTarget(explorerMenu.target); setExplorerMenu(null); }}>Download</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { showProperties(explorerMenu.target); setExplorerMenu(null); }}>Properties</button>
                </>
              ) : (
                <>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { createFile(explorerMenu.target.path); setExplorerMenu(null); }}>New File</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { setExplorerMenu(null); window.alert('New folder is ready for backend file-system creation.'); }}>New Folder</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { setExplorerMenu(null); }}>Paste</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { renameTarget(explorerMenu.target); setExplorerMenu(null); }}>Rename</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5 text-red-300" onClick={() => { requestDelete(explorerMenu.target); setExplorerMenu(null); }}>Delete</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5 text-white/70" onClick={() => { setExplorerMenu(null); }}>Collapse</button>
                  <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { showProperties(explorerMenu.target); setExplorerMenu(null); }}>Properties</button>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {pendingAction && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
              onClick={() => setPendingAction(null)}
            >
              <motion.div
                initial={{ scale: 0.96, y: 12 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.96, y: 12 }}
                className="w-full max-w-md rounded-2xl border border-[rgba(0,255,255,0.12)] bg-[#111827] p-5 shadow-2xl text-white"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="text-[10px] uppercase tracking-[0.3em] text-[#00E5FF]">{pendingAction.mode === 'delete' ? 'Delete Confirmation' : 'Unsaved Changes'}</div>
                <div className="mt-3 text-sm font-semibold">{pendingAction.mode === 'delete' ? `Delete ${pendingAction.target.kind === 'folder' ? 'Folder' : 'File'}?` : `Save changes to ${pendingAction.target.label}?`}</div>
                <div className="mt-2 text-sm text-white">{pendingAction.target.label}</div>
                <div className="mt-2 text-[11px] text-white/60">{pendingAction.mode === 'delete' ? (pendingAction.target.kind === 'folder' ? 'Delete all contents? This action cannot be undone.' : 'This action cannot be undone.') : 'Choose how to handle unsaved changes before closing.'}</div>
                <div className="mt-5 flex justify-end gap-2">
                  <button className="rounded-md border border-[rgba(0,255,255,0.12)] px-4 py-2 text-[11px] text-white/70 hover:text-white hover:bg-white/5" onClick={() => resolvePendingAction('cancel')}>Cancel</button>
                  {pendingAction.mode === 'delete' ? (
                    <>
                      <button className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-2 text-[11px] text-red-200 hover:bg-red-500/20" onClick={() => resolvePendingAction('delete')}>Delete</button>
                    </>
                  ) : (
                    <>
                      <button className="rounded-md border border-[rgba(0,255,255,0.12)] px-4 py-2 text-[11px] text-white/70 hover:text-white hover:bg-white/5" onClick={() => resolvePendingAction('discard')}>Discard</button>
                      <button className="rounded-md border border-[#00E5FF]/30 bg-[#00E5FF]/10 px-4 py-2 text-[11px] text-[#00E5FF] hover:bg-[#00E5FF]/20" onClick={() => resolvePendingAction('save')}>Save</button>
                    </>
                  )}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      
      {/* Footer Status Bar */}
      <div className="h-6 bg-[#007acc] border-t border-[#005c99] flex flex-shrink-0 items-center justify-between px-3 text-[10.5px] font-mono text-white tracking-wide z-30 shadow-[0_-2px_10px_rgba(0,0,0,0.2)] relative">
         <div className="absolute top-0 right-0 h-px w-64 bg-gradient-to-l from-white/30 to-transparent animate-[pulse_3s_ease-in-out_infinite]" />
         <div className="flex items-center gap-4 relative z-10">
           <span className="flex items-center gap-2 font-bold"><Monitor className="w-3.5 h-3.5" /> NEUROS 2.4</span>
           <span className="flex items-center gap-1 hover:bg-[#111827]/20 px-2 py-0.5 rounded cursor-pointer transition-colors"><Check className="w-3 h-3"/> 0</span>
           <span className="flex items-center gap-1 hover:bg-[#111827]/20 px-2 py-0.5 rounded cursor-pointer transition-colors text-yellow-300"><Bug className="w-3 h-3"/> 0</span>
         </div>
         <div className="flex items-center gap-4 relative z-10">
           {isCompiling && <span className="animate-pulse ">Compiling Sketch...</span>}
           {isUploading && <span className="animate-pulse ">Uploading...</span>}
           <span className="hover:bg-[#111827]/20 px-2 py-0.5 rounded cursor-pointer transition-colors">Ln 14, Col 35</span>
           <span className="hover:bg-[#111827]/20 px-2 py-0.5 rounded cursor-pointer transition-colors">Spaces: 2</span>
           <span className="hover:bg-[#111827]/20 px-2 py-0.5 rounded cursor-pointer transition-colors">UTF-8</span>
           <span className="hover:bg-[#111827]/20 px-2 py-0.5 rounded cursor-pointer transition-colors font-bold uppercase">{activeContent?.language || 'TEXT'}</span>
         </div>
      </div>
    </div>
  );
}

// Menu Components
function MenuItem({ label, shortcut, onClick, hasSubmenu }: { label: string, shortcut?: string, onClick?: () => void, hasSubmenu?: boolean }) {
    return (
        <button onClick={onClick} className="w-full text-left px-4 py-1.5 text-[11px] hover:bg-[#007acc] hover:text-white text-white transition-colors flex justify-between items-center group">
            <span>{label}</span>
            {(shortcut || hasSubmenu) && (
              <span className="text-white/50 group-hover:text-white/70 ml-6 flex items-center justify-end">
                {shortcut}
                {hasSubmenu && <ChevronRight className="w-3 h-3 ml-2" />}
              </span>
            )}
        </button>
    );
}

function MenuDivider() {
    return <div className="h-px bg-[rgba(0,255,255,0.08)] my-1" />;
}

// Sidebar Components
function TreeFolder({ title, defaultExpanded, children, onContextMenu, onDrop }: { title: string, defaultExpanded?: boolean, children?: React.ReactNode, onContextMenu?: (event: React.MouseEvent<HTMLDivElement>) => void, onDrop?: () => void }) {
    const [expanded, setExpanded] = useState(defaultExpanded);
    return (
        <div>
            <div 
                className="flex items-center gap-2 px-2 py-1 rounded-md cursor-pointer transition-colors text-[11px] font-mono tracking-wide text-white hover:bg-[#161B22] hover:text-white group"
                onClick={() => setExpanded(!expanded)}
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onContextMenu?.(event);
        }}
        onDragOver={(event) => {
          if (onDrop) {
            event.preventDefault();
          }
        }}
        onDrop={(event) => {
          if (onDrop) {
            event.preventDefault();
            event.stopPropagation();
            onDrop();
          }
        }}
            >
                <ChevronRight className={`w-3 h-3 shrink-0 transition-transform text-white/50 group-hover:text-white ${expanded ? 'rotate-90' : ''}`} />
                <Folder className="w-3.5 h-3.5 shrink-0 text-[#8a8a8d]" strokeWidth={1.5} />
                <span className="overflow-hidden text-ellipsis whitespace-nowrap leading-none pt-px select-none">{title}</span>
            </div>
            {expanded && (
                <div className="pl-3.5 ml-2 border-l border-[rgba(0,255,255,0.08)]/50 space-y-[1px] mt-[1px]">
                    {children}
                </div>
            )}
        </div>
    );
}

function TreeFile({ title, active, selected, onClick, onContextMenu, onDragStart }: { title: string, active?: boolean, selected?: boolean, onClick?: (event: React.MouseEvent<HTMLDivElement>) => void, onContextMenu?: (event: React.MouseEvent<HTMLDivElement>) => void, onDragStart?: () => void }) {
    return (
        <div 
            onClick={onClick}
      draggable
      onDragStart={onDragStart}
      onContextMenu={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onContextMenu?.(event);
      }}
      className={`flex items-center gap-2 px-2 py-1 ml-3 rounded-md cursor-pointer transition-colors text-[11px] font-mono tracking-wide select-none ${active || selected ? 'bg-[#00E5FF]/10 text-[#00E5FF] font-bold border border-[#00E5FF]/20' : 'text-white hover:bg-[#161B22] hover:text-white border border-transparent'}`}
        >
            <File className={`w-3 h-3 shrink-0 ${active ? 'text-[#00E5FF]' : 'text-white/50'}`} strokeWidth={active ? 2 : 1.5} />
            <span className="overflow-hidden text-ellipsis whitespace-nowrap leading-none pt-px">{title}</span>
        </div>
    );
}
