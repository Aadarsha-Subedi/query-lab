import { Text } from '@/components/typography/Text'

import { IssuesLink, LegalList, LegalPage, LegalSection } from './LegalPage'

/** Every statement here describes the code as it is; change it together with the backend. */
export function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <LegalSection title="What is collected">
        <LegalList>
          <li>
            <strong>Your sign-in.</strong> You sign in with Google or GitHub, so there is no password.
            Querylab stores your name, your email and your provider account id, and keeps the basic profile
            your provider returns, which includes a link to your profile picture.
          </li>
          <li>
            <strong>Cookies.</strong> A session cookie keeps you signed in and a CSRF cookie protects forms.
            Your light or dark theme choice stays in your browser.
          </li>
          <li>
            <strong>What you ask.</strong> Your questions, the SQL, each step the agent took, a preview of up
            to a few result rows, the model used, token counts and timings. Your thumbs up or down and any
            note you add are kept with the run.
          </li>
          <li>
            <strong>Your LLM key, if you add one.</strong> It is stored encrypted. Querylab only shows you its
            last 4 characters.
          </li>
          <li>
            <strong>Your workspaces, if you create any.</strong> The tables and rows from the dumps you
            import.
          </li>
          <li>
            <strong>Server logs.</strong> Each request is logged with its route, headers, request body, your
            user id and timings. Keys, tokens and cookies are removed first, but your question text is in the
            body, and the headers can show your IP address. Your IP address is also used to rate-limit
            signed-out requests.
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="How it is used">
        <LegalList>
          <li>To run the service: answer your questions, show your history and enforce the limits.</li>
          <li>
            To measure and improve the answers, using runs on the shared demo workspace only. A run that
            failed, was edited or got a thumbs down can be drafted into an eval case. Staff can read these
            traces without your user id or email attached, and a reviewed case can end up in the eval set or
            in a training set for a fine-tuned model.
          </li>
          <li>
            Runs on your private workspaces are left out of evals and of the staff screens. The person who
            runs Querylab still has access to the database itself.
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="Your uploaded dumps">
        <Text>
          Your browser uploads a dump straight to Cloudflare R2 storage. A background job loads it into your
          workspace&apos;s own database schema, then deletes the file, whether the import worked or failed. An
          upload you never finished is cleaned up by a storage rule after about a day. The loaded tables stay
          until you delete the workspace.
        </Text>
      </LegalSection>

      <LegalSection title="Who else receives data">
        <LegalList>
          <li>
            <strong>Google or GitHub</strong>, whichever you sign in with, for sign-in.
          </li>
          <li>
            <strong>The LLM provider.</strong> That is Groq on the shared key, or the provider of your own key
            (Google or OpenAI). It receives your question and the workspace&apos;s schema, which means table
            and column names, comments, and common values from text columns with few distinct values. It also
            receives the SQL and any error. When the agent checks a result that looks odd, it receives a few
            result rows too. This applies to private workspaces as well as the demo. Each provider&apos;s own
            terms apply, and on a free tier they may let the provider use what it receives to improve its
            products.
          </li>
          <li>
            <strong>Cloudflare</strong> hosts the app and stores uploads. <strong>Neon</strong> hosts the
            Postgres database.
          </li>
        </LegalList>
        <Text>Querylab shows no ads, sells no data and uses no tracking or analytics scripts.</Text>
      </LegalSection>

      <LegalSection title="Keeping and deleting your data">
        <LegalList>
          <li>
            There is no fixed retention period yet. Data stays until it is deleted or the project is wiped.
          </li>
          <li>
            You can delete a private workspace yourself, which removes its tables. Your runs on it stay in
            your history, including their questions, SQL and previews.
          </li>
          <li>
            There is no button to delete your account or your runs. To ask for that,{' '}
            <IssuesLink>open an issue on GitHub</IssuesLink> without putting anything private in it.
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="Contact">
        <Text>
          Questions about this policy go to <IssuesLink>GitHub issues</IssuesLink>. This page is a
          plain-English description of a hobby project, not legal advice.
        </Text>
      </LegalSection>
    </LegalPage>
  )
}
