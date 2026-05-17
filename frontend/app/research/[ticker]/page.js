import Link from "next/link";
import { getResearch } from "../../../lib/api";
import Dashboard from "./Dashboard";
import NotIngestedYet from "./NotIngestedYet";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { ticker } = await params;
  const t = (ticker || "").toUpperCase();
  return {
    title: `${t} — Diligence`,
    description: `Adversarial multi-agent due diligence on ${t}: bull case, bear case, disputed facts ranked by materiality.`,
  };
}

export default async function ResearchPage({ params }) {
  const { ticker } = await params;
  const t = (ticker || "").toUpperCase();

  let payload;
  try {
    payload = await getResearch(t);
  } catch (err) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
        <h1 className="font-display text-3xl text-destructive">Backend unreachable</h1>
        <p className="mt-3 font-mono text-sm text-foreground/70">{String(err.message || err)}</p>
        <Link href="/" className="mt-6 font-mono text-sm text-accent underline">
          ← back home
        </Link>
      </main>
    );
  }

  // null payload means GET 404'd — ticker has no cache. Render the
  // run-pipeline CTA inline instead of dead-ending on notFound().
  if (!payload) {
    return <NotIngestedYet ticker={t} />;
  }

  return <Dashboard ticker={t} payload={payload} />;
}
