import Link from "next/link";
import { SiteShell } from "@/components/workspace/site-shell";
import s from "@/components/workspace/simple-workspace.module.css";

export default function PricingPage() {
  return <SiteShell><div className={s.guide}>
    <p className={s.kicker}>PLANS</p>
    <h1>Start with the free workspace.</h1>
    <p className={s.intro}>Explore Furnace now. Managed infrastructure is the next stage.</p>
    <section className={s.guideStep} aria-labelledby="free-title">
      <span className={s.stepNumber}>✓</span><div>
        <h2 id="free-title">Local preview · Free</h2>
        <p>Inspect model metadata, save your setup and cases, export a starter kit, and
          try the optional infrastructure example. Run a reviewed model recipe locally in Docker,
          or connect a text-chat server you already operate.</p>
        <p className={s.small}>Requires Python 3.12 and uv. The fixture needs Docker;
          the manual connector needs your own running server. Model support is limited to
          the recorded recipe, version and hardware combinations; it is not universal compatibility.</p>
        <Link href="/start" className={s.topAction}>Get started →</Link>
      </div>
    </section>
    <section className={s.guideStep} aria-labelledby="managed-title">
      <span className={s.stepNumber}>○</span><div>
        <h2 id="managed-title">Managed infrastructure · Planned $20/month</h2>
        <p>The direction is to provide the server, logs, monitoring, evaluation harness
          and operational support around supported models.</p>
        <p>Billing and cloud provisioning are inactive. This service is not available
          to purchase. Hosting, usage limits and supported models must be defined and
          validated before launch.</p>
      </div>
    </section>
  </div></SiteShell>;
}
