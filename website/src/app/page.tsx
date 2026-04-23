import { getIndexContent } from '@/lib/content'
import Link from 'next/link'

export default async function HomePage() {
  const doc = await getIndexContent()
  
  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-sun-500/10 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-sun-600/10 rounded-full blur-3xl" />
        </div>
        
        <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-sun-500/10 border border-sun-500/20 text-sun-400 text-sm font-mono mb-8">
            <span className="w-2 h-2 rounded-full bg-sun-400 animate-pulse" />
            Self-Improving AI Agent
          </div>
          
          <h1 className="text-5xl md:text-7xl font-display font-bold text-void-100 mb-6 tracking-tight">
            Sun <span className="text-sun-400">CLI</span>
          </h1>
          
          <p className="text-xl text-void-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            一个会自己进化的 AI Agent。Memory 记住你是谁，Skill 记住怎么做事，
            Nudge Engine 保证这个循环不停转。
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link 
              href="/design"
              className="px-8 py-3 rounded-lg bg-sun-500 text-void-950 font-semibold hover:bg-sun-400 transition-colors"
            >
              查看设计思路
            </Link>
            <a 
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-3 rounded-lg border border-void-700 text-void-300 hover:border-sun-500/50 hover:text-sun-400 transition-colors"
            >
              GitHub
            </a>
          </div>
        </div>
      </section>
      
      {/* Content from Markdown */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto px-6">
          <article 
            className="prose prose-invert prose-lg max-w-none"
            dangerouslySetInnerHTML={{ __html: doc.html }}
          />
        </div>
      </section>
    </main>
  )
}
