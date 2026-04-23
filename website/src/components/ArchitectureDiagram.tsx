'use client'

import { motion } from 'framer-motion'

const nodes = [
  { id: 'user', label: 'User Input', x: 50, y: 5, type: 'input' },
  { id: 'chat', label: 'ChatSession\n(Main Agent)', x: 50, y: 25, type: 'core' },
  { id: 'tool', label: 'Tool Loop\n(10 iter max)', x: 20, y: 45, type: 'module' },
  { id: 'nudge', label: 'NudgeEngine\n(Counters)', x: 50, y: 45, type: 'module' },
  { id: 'skill', label: 'SkillManagerV2\n(Progressive)', x: 80, y: 45, type: 'module' },
  { id: 'review', label: 'Review Agent\n(Background)', x: 50, y: 65, type: 'core' },
  { id: 'memory', label: '.memory/\n(Capacity 2200c)', x: 25, y: 85, type: 'storage' },
  { id: 'skills', label: '.skills/\n(Lifecycle)', x: 50, y: 85, type: 'storage' },
  { id: 'security', label: 'SecurityScanner\n(Threat + Rollback)', x: 75, y: 85, type: 'storage' },
]

const connections = [
  ['user', 'chat'],
  ['chat', 'tool'],
  ['chat', 'nudge'],
  ['chat', 'skill'],
  ['nudge', 'review'],
  ['review', 'memory'],
  ['review', 'skills'],
  ['skill', 'skills'],
  ['chat', 'security'],
]

export default function ArchitectureDiagram() {
  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[600px] relative h-[500px]">
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          {connections.map(([from, to], i) => {
            const fromNode = nodes.find(n => n.id === from)
            const toNode = nodes.find(n => n.id === to)
            if (!fromNode || !toNode) return null
            return (
              <motion.line
                key={i}
                x1={fromNode.x}
                y1={fromNode.y}
                x2={toNode.x}
                y2={toNode.y}
                stroke="rgba(245, 158, 11, 0.2)"
                strokeWidth="0.3"
                initial={{ pathLength: 0 }}
                whileInView={{ pathLength: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 1, delay: i * 0.1 }}
              />
            )
          })}
        </svg>
        
        {nodes.map((node, i) => (
          <motion.div
            key={node.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
          >
            <div className={`
              px-4 py-2 rounded-lg text-xs font-mono text-center whitespace-pre-line border
              ${node.type === 'core' ? 'bg-sun-500/10 border-sun-500/30 text-sun-300' : ''}
              ${node.type === 'module' ? 'bg-void-800/50 border-void-700 text-void-300' : ''}
              ${node.type === 'storage' ? 'bg-void-900/80 border-void-700/50 text-void-400' : ''}
              ${node.type === 'input' ? 'bg-void-800 border-void-600 text-void-200' : ''}
            `}>
              {node.label}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
