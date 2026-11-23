"use client";
import Image from "next/image";
import { useState } from "react";
import { DocPage } from "./site";
import type { Recording } from "@/lib/recording";
import captured from "@/public/product/capture.json";

const steps = [
  { title: "1. Install for your account", image: "installer.png", text: "An actual Windows installer capture. The app bundles its own Python runtime and dependencies; no developer tools are required to use it." },
  { title: "2. Open your local workspace", image: "studio-home.png", text: "A real installed-app capture. Studio opened locally; no model was running. Inspect projects and export a kit without Docker." },
  { title: "3. Explore the guided example", image: "studio-example.png", text: "Recorded metadata from the installed app, not an LLM. Fixture execution needs Docker and is separate from model inference." },
];
export function InstalledTour({recording}: {recording: Recording | null}) {
  const tourSteps = recording ? [...steps,
    {title:"4. Prepare a pinned model",image:"generated/prepared.png",text:"Actual Qwen CPU preparation using cached assets, with explicit consent and weight verification."},
    {title:"5. Ask and evaluate",image:"generated/evaluated.png",text:"Real installed-model evaluation. Failed cases remain visible; a rule score is not semantic quality."},
    {title:"6. Observe the crash",image:"generated/crashed.png",text:"The test killed only this model container during a running batch. The interrupted attempt and error remain."},
    {title:"7. Restart and compare",image:"generated/reproducibility.png",text:"Explicit health refresh, consent and restart, followed by a new completed batch. The displayed comparison is actual, not a prediction."},
  ] : steps;
  const [selected, setSelected] = useState(0);
  const step = tourSteps[selected];
  const size = step.image.startsWith("generated/") ? recording!.image_sizes[step.image.slice(10).replace(".png", "")] : (captured.dimensions as Record<string, number[]>)[step.image];
  return <DocPage title="A look inside your local workspace." eyebrow="RECORDED SCREENSHOTS · NOT A LIVE SESSION"><p>This tour uses screenshots from an installed-app smoke run. It does not start a server, send prompts or run inference.</p><div className="tour-nav" role="group" aria-label="Tour steps">{tourSteps.map((item, index) => <button key={item.title} aria-pressed={selected === index} onClick={() => setSelected(index)}>{item.title}</button>)}</div><section aria-live="polite"><h2>{step.title}</h2><Image unoptimized src={"/product/" + step.image} alt={step.title + ". " + step.text} width={size[0]} height={size[1]} /><p>{step.text}</p></section><h2>Recorded installed-model journey</h2>{recording ? <><video controls preload="metadata" poster="/product/generated/prepared.png" aria-label="Recorded installed Qwen CPU journey"><source src={"/product/generated/"+recording.video} type="video/webm"/><track kind="captions" src="/product/generated/captions.vtt" srcLang="en" label="English" default/></video><p>Uncut automated browser recording from installed source <code>{recording.source_commit.slice(0,7)}</code>, using cached assets. Real inference, not the fixture. Installer/launcher steps are separate real still captures, not installation footage.</p><p>Actual results: {recording.rule_passed}/{recording.rule_total} rule checks passed; {recording.identical}/{recording.compared} outputs identical across launches. Failed answers remain. Reproducibility is not correctness.</p><p><a href="/product/generated/record.json">Local recording evidence</a> · <a href={"/product/generated/"+recording.video} download>Download the local WebM</a></p></> : <p>The real-model recording is not staged in this build. The screenshots above are actual installed-app metadata. An operator can stage an executed local recording using the source instructions; no model video is fabricated or substituted here.</p>}<p><a href="https://github.com/dilipna/Furnace4LLM/blob/main/docs/product/real-model-validation.md">Historical Qwen and Granite records ↗</a></p></DocPage>;
}
