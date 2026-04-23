import type { Metadata } from 'next'
import { Playfair_Display, JetBrains_Mono, Bricolage_Grotesque } from 'next/font/google'
import './globals.css'

const playfair = Playfair_Display({
  subsets: ['latin'],
  variable: '--font-playfair',
  display: 'swap',
})

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
})

const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  variable: '--font-geist',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Sun CLI — Self-Improving AI Agent',
  description: 'A CLI AI agent that learns from experience. The more you use it, the smarter it gets.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" className={`${playfair.variable} ${jetbrains.variable} ${bricolage.variable}`}>
      <head>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css" />
      </head>
      <body className="font-sans min-h-screen">
        <Navigation />
        {children}
        <Footer />
      </body>
    </html>
  )
}

function Navigation() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-void-800/50 bg-void-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sun-400 to-sun-600 flex items-center justify-center">
            <span className="text-void-950 font-bold text-sm">S</span>
          </div>
          <span className="font-display text-xl font-bold text-void-100 group-hover:text-sun-400 transition-colors">
            Sun CLI
          </span>
        </a>
        
        <div className="flex items-center gap-8">
          <a href="/" className="nav-link text-sm font-medium">首页</a>
          <a href="/design" className="nav-link text-sm font-medium">设计思路</a>
          <a 
            href="https://github.com" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-sm font-medium text-void-400 hover:text-sun-400 transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            GitHub
          </a>
        </div>
      </div>
    </nav>
  )
}

function Footer() {
  return (
    <footer className="border-t border-void-800/50 mt-32">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-sun-400 to-sun-600 flex items-center justify-center">
              <span className="text-void-950 font-bold text-xs">S</span>
            </div>
            <span className="text-void-400 text-sm">Sun CLI — 自进化 AI Agent</span>
          </div>
          <p className="text-void-600 text-sm">
            Inspired by Hermes Agent & Claude Code
          </p>
        </div>
      </div>
    </footer>
  )
}
