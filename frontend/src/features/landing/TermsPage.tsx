import { Link } from '@tanstack/react-router'

import { Text } from '@/components/typography/Text'

import { IssuesLink, legalLink, LegalList, LegalPage, LegalSection } from './LegalPage'
import { OLIST_LICENCE_URL } from './links'

export function TermsPage() {
  return (
    <LegalPage title="Terms">
      <LegalSection title="Using Querylab">
        <Text>By signing in, you agree to these terms. Please:</Text>
        <LegalList>
          <li>Do not abuse the service or use it to harm anyone.</li>
          <li>Do not attack it, probe it for weaknesses or try to reach other people&apos;s data.</li>
          <li>Respect the rate limits and the daily limit on the shared key, and do not work around them.</li>
        </LegalList>
        <Text>An account that breaks these terms can be removed.</Text>
      </LegalSection>

      <LegalSection title="Your data">
        <Text>
          What you upload stays yours. By uploading a dump, you confirm you are allowed to, and you accept
          that parts of it go to an LLM provider as the{' '}
          <Link to="/privacy" className={legalLink}>
            Privacy Policy
          </Link>{' '}
          describes.
        </Text>
      </LegalSection>

      <LegalSection title="The demo dataset">
        <Text>
          The demo workspace is built from the Olist Brazilian e-commerce dataset, licensed{' '}
          <a href={OLIST_LICENCE_URL} target="_blank" rel="noreferrer" className={legalLink}>
            CC BY-NC-SA 4.0
          </a>
          . You may not use it commercially.
        </Text>
      </LegalSection>

      <LegalSection title="AI answers can be wrong">
        <Text>
          The SQL and the answers come from an AI model and can be wrong, even when they look right or carry a
          &quot;checked&quot; label. Check them before you rely on them.
        </Text>
      </LegalSection>

      <LegalSection title="No warranty, limited liability">
        <Text>
          Querylab is provided as it is, with no warranty of any kind. As far as the law allows, its author is
          not liable for any loss that comes from using it, including lost data and decisions made from its
          answers.
        </Text>
      </LegalSection>

      <LegalSection title="Changes and ending the service">
        <Text>
          These terms and the service can change, and the service can end at any time, with or without notice.
        </Text>
      </LegalSection>

      <LegalSection title="Contact">
        <Text>
          Questions go to <IssuesLink>GitHub issues</IssuesLink>. These terms are plain English written for a
          hobby project, not legal advice.
        </Text>
      </LegalSection>
    </LegalPage>
  )
}
