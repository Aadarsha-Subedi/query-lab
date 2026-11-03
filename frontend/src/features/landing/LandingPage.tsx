import { CtaBand } from './CtaBand'
import { EvalStrip } from './EvalStrip'
import { Faq } from './Faq'
import { Features } from './Features'
import { Hero } from './Hero'
import { HowItWorks } from './HowItWorks'
import { SiteChrome } from './SiteChrome'

export function LandingPage() {
  return (
    <SiteChrome glow>
      <Hero />
      <HowItWorks />
      <Features />
      <EvalStrip />
      <Faq />
      <CtaBand />
    </SiteChrome>
  )
}
