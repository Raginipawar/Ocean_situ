import { Reveal } from "../components/Reveal";

const TIMELINE = [
  { stage: "Stage 1", label: "Internal SIH (i-SIH), Round 1 — Pitch", detail: "PPT + verbal explanation. Complete." },
  { stage: "Stage 2", label: "Internal SIH, Round 2 — Offline, 70% working", detail: "The 4-day core build (Sept 5–8, 2026): contracts → real data → full integration → frontend blitz." },
  { stage: "Stage 3", label: "Push to 100%", detail: "Polish, Nowcast Engine if time allows, backup demo video, before ~30 Sept national portal submission." },
  { stage: "Stage 4", label: "National screening", detail: "October 2026 — evaluated on originality, scalability, technical implementation, real-world impact." },
  { stage: "Stage 5", label: "Mentoring window", detail: "If shortlisted, Oct–Dec 2026 — refine with expert/faculty mentors, harden prototype." },
  { stage: "Stage 6", label: "Grand Finale", detail: "December 2026 — 36-hour non-stop build: integration, polish, live-data hookup, pitch rehearsal." },
];

export function About() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-32">
      <Reveal>
        <p className="font-nav text-xs opacity-60">Smart India Hackathon 2026 · Team Hudson Hackers</p>
        <h1 className="font-display mt-3 text-5xl sm:text-6xl">About VARUNA</h1>
      </Reveal>

      <Reveal className="mt-10 space-y-4 text-sm opacity-80">
        <p>
          <strong>Problem Statement ID:</strong> SIH26067
        </p>
        <p>
          <strong>Problem Statement Title:</strong> Develop a web-based interactive 3D visualization
          platform that integrates numerical ocean model outputs and in-situ observations.
        </p>
        <p>
          <strong>Theme:</strong> Disaster Management · <strong>PS Category:</strong> Software ·{" "}
          <strong>Ministry:</strong> Earth Sciences (MoES)
        </p>
        <p>
          <strong>Project name:</strong> VARUNA — Visualization &amp; Assimilation of Real-time
          Underwater Network Analytics
        </p>
      </Reveal>

      <Reveal className="mt-16">
        <h2 className="font-display text-3xl">Who this is for</h2>
        <p className="mt-4 text-sm opacity-75">
          Fishermen, the Indian Navy, Coast Guard, shipping and offshore operators, coastal disaster
          management authorities, and ocean researchers validating models. The dual expert/public
          mode on the Digital Twin exists specifically so the same tool serves a researcher reading
          raw confidence stats and a fisherman reading a simple safe / caution / avoid signal.
        </p>
      </Reveal>

      <Reveal className="mt-16">
        <h2 className="font-display text-3xl">Delivery timeline</h2>
        <div className="mt-8 space-y-6">
          {TIMELINE.map((row) => (
            <div key={row.stage} className="flex flex-col gap-1 border-b pb-6 sm:flex-row sm:gap-8" style={{ borderColor: "var(--color-border)" }}>
              <span className="font-nav w-24 shrink-0 text-xs opacity-50">{row.stage}</span>
              <div>
                <h3 className="font-nav text-sm">{row.label}</h3>
                <p className="mt-1 text-sm opacity-70">{row.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Reveal>
    </div>
  );
}
