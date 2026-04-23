import { getDesignDocs } from '@/lib/content'
import DesignClient from './DesignClient'

export default async function DesignPage() {
  const docs = await getDesignDocs()
  
  const serializedDocs = docs.map(d => ({
    slug: d.slug,
    title: d.title,
    html: d.html,
  }))
  
  return <DesignClient docs={serializedDocs} />
}
