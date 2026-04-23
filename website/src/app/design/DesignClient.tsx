'use client'

import { useState } from 'react'

interface DesignDoc {
  slug: string
  title: string
  html: string
}

export default function DesignClient({ docs }: { docs: DesignDoc[] }) {
  const [activeSlug, setActiveSlug] = useState(docs[0]?.slug || '')
  const activeDoc = docs.find(d => d.slug === activeSlug)
  
  return (
    <div className="min-h-screen pt-16">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="flex flex-col lg:flex-row gap-12">
          {/* Sidebar Navigation */}
          <aside className="lg:w-72 flex-shrink-0">
            <div className="sticky top-24">
              <h2 className="text-lg font-semibold text-void-200 mb-6 font-display">
                设计思路
              </h2>
              <nav className="space-y-1">
                {docs.map((doc) => (
                  <button
                    key={doc.slug}
                    onClick={() => setActiveSlug(doc.slug)}
                    className={`w-full text-left px-4 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                      activeSlug === doc.slug
                        ? 'bg-sun-500/10 text-sun-400 border border-sun-500/20'
                        : 'text-void-400 hover:text-void-200 hover:bg-void-800/50'
                    }`}
                  >
                    {doc.title}
                  </button>
                ))}
              </nav>
            </div>
          </aside>
          
          {/* Main Content */}
          <main className="flex-1 min-w-0">
            {activeDoc ? (
              <article 
                className="prose prose-invert prose-lg max-w-none"
                dangerouslySetInnerHTML={{ __html: activeDoc.html }}
              />
            ) : (
              <div className="text-void-500">选择一个文档查看</div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}
