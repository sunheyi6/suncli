'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

const TYPING_SPEED = 40

const codeLines = [
  { prompt: '$ ', text: 'suncli deploy flask-app to k8s', delay: 500 },
  { prompt: '> ', text: 'Analyzing project structure...', delay: 800, output: true },
  { prompt: '> ', text: 'Loading skill: flask-k8s-deploy', delay: 600, output: true, highlight: true },
  { prompt: '> ', text: 'Step 1/6: Creating Dockerfile with gunicorn', delay: 400, output: true },
  { prompt: '> ', text: 'Step 2/6: Building and pushing image...', delay: 400, output: true },
  { prompt: '> ', text: 'Step 3/6: Writing deployment.yaml', delay: 400, output: true },
  { prompt: '> ', text: 'Step 4/6: kubectl apply deployment', delay: 400, output: true },
  { prompt: '> ', text: 'Step 5/6: Verifying pod status...', delay: 400, output: true },
  { prompt: '> ', text: 'Step 6/6: Deployment successful', delay: 400, output: true, success: true },
  { prompt: '', text: '', delay: 1000 },
  { prompt: '$ ', text: 'suncli skill list', delay: 800 },
  { prompt: '> ', text: 'flask-k8s-deploy [devops]: Deploy Flask to K8s (uses: 1, success: 100%)', delay: 400, output: true, highlight: true },
]

export default function Terminal() {
  const [displayedLines, setDisplayedLines] = useState<string[]>([])
  const [currentLine, setCurrentLine] = useState(0)
  const [currentChar, setCurrentChar] = useState(0)

  useEffect(() => {
    if (currentLine >= codeLines.length) return

    const line = codeLines[currentLine]
    const fullText = line.prompt + line.text

    if (currentChar < fullText.length) {
      const timer = setTimeout(() => {
        setCurrentChar(c => c + 1)
      }, TYPING_SPEED)
      return () => clearTimeout(timer)
    } else {
      const timer = setTimeout(() => {
        setDisplayedLines(prev => [...prev, fullText])
        setCurrentLine(l => l + 1)
        setCurrentChar(0)
      }, line.delay)
      return () => clearTimeout(timer)
    }
  }, [currentLine, currentChar])

  const renderLine = (text: string, index: number) => {
    const line = codeLines[index]
    if (!line) return text

    if (line.success) {
      return <span className="text-emerald-400">{text}</span>
    }
    if (line.highlight) {
      return <span className="text-sun-400">{text}</span>
    }
    if (line.output) {
      return <span className="text-void-400">{text}</span>
    }
    return <span className="text-void-200">{text}</span>
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 0.4 }}
      className="terminal-window w-full max-w-2xl mx-auto"
    >
      <div className="terminal-header">
        <div className="terminal-dot bg-red-500/80" />
        <div className="terminal-dot bg-yellow-500/80" />
        <div className="terminal-dot bg-emerald-500/80" />
        <span className="ml-2 text-xs text-void-500 font-mono">sun-cli — zsh</span>
      </div>
      <div className="terminal-body text-void-300 min-h-[320px]">
        {displayedLines.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap break-all">
            {renderLine(line, i)}
          </div>
        ))}
        {currentLine < codeLines.length && (
          <div className="whitespace-pre-wrap break-all">
            <span className={codeLines[currentLine].output ? 'text-void-400' : 'text-void-200'}>
              {codeLines[currentLine].prompt + codeLines[currentLine].text.slice(0, currentChar)}
            </span>
            <span className="inline-block w-2 h-4 bg-sun-500 ml-0.5 animate-pulse" />
          </div>
        )}
      </div>
    </motion.div>
  )
}
