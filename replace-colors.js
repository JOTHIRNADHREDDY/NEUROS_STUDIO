const fs = require('fs');
const glob = require('glob');
const path = require('path');

const files = glob.sync('{app,components}/**/*.tsx');

const colorMap = {
  // backgrounds
  'bg-[#0a0a0b]': 'bg-white',
  'bg-[#121214]': 'bg-gray-50',
  'bg-[#1a1a1d]': 'bg-white',
  'bg-[#222225]': 'bg-white',
  'bg-[#2a2a2d]': 'bg-gray-200',
  'bg-transparent': 'bg-transparent',
  // text colors
  'text-[#d1d1d1]': 'text-gray-900',
  'text-[#a1a1a1]': 'text-gray-800',
  'text-[#5a5a5d]': 'text-gray-500',
  'text-white': 'text-gray-900',
  'text-zinc-500': 'text-gray-500',
  // borders
  'border-[#1a1a1d]': 'border-gray-200',
  'border-[#2a2a2d]': 'border-gray-200',
  'border-[#3a3a3d]': 'border-gray-300',
  // hover backgrounds
  'hover:bg-[#1a1a1d]': 'hover:bg-gray-100',
  'hover:bg-[#2a2a2d]': 'hover:bg-gray-200',
  'hover:bg-[#121214]': 'hover:bg-gray-50',
  // Theme specific syntax highlighting
  'text-[#9cdcfe]': 'text-purple-600',
  'text-[#b5cea8]': 'text-green-600',
  'text-[#569cd6]': 'text-blue-600',
  'text-[#dcdcaa]': 'text-yellow-600',
};

files.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');
  let newContent = content;
  
  // Custom hacks
  newContent = newContent.replace(/vs-dark/g, 'light');
  newContent = newContent.replace(/from-\[\#00f2ff\]\/5/g, 'from-[#00f2ff]/10');
  
  Object.keys(colorMap).forEach(key => {
    // Replace whole words/classes exactly so we don't accidentally match parts
    // but wait, some are like text-[#d1d1d1]
    const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(?<=\\s|['"])${escapeRegex(key)}(?=\\s|['"]|/|\\b)`, 'g');
    newContent = newContent.replace(regex, colorMap[key]);
  });
  
  // also standard replaces
  Object.keys(colorMap).forEach(key => {
    newContent = newContent.split(key).join(colorMap[key]);
  });

  if (content !== newContent) {
    fs.writeFileSync(file, newContent, 'utf8');
    console.log(`Updated ${file}`);
  }
});
