'use client'

import { motion } from 'framer-motion'
import { LucideIcon } from 'lucide-react'

interface FeatureCardProps {
  icon: LucideIcon
  title: string
  subtitle: string
  description: string
  index: number
}

export default function FeatureCard({ icon: Icon, title, subtitle, description, index }: FeatureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.6, delay: index * 0.1 }}
      className="gradient-border p-6 md:p-8 group card-hover"
    >
      <div className="flex items-start justify-between mb-6">
        <div className="w-12 h-12 rounded-xl bg-sun-500/10 border border-sun-500/20 flex items-center justify-center group-hover:bg-sun-500/20 transition-colors duration-500">
          <Icon className="w-6 h-6 text-sun-400" />
        </div>
        <span className="text-void-700 font-mono text-sm">0{index + 1}</span>
      </div>
      
      <h3 className="text-xl font-semibold text-void-100 mb-1 group-hover:text-sun-400 transition-colors duration-300">
        {title}
      </h3>
      <p className="text-sun-500/70 text-sm font-mono mb-4">{subtitle}</p>
      <p className="text-void-400 text-sm leading-relaxed">{description}</p>
    </motion.div>
  )
}
