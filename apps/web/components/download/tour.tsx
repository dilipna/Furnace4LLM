"use client";
import { useState } from "react";
import { DocPage } from "./site";

const steps = [
  { title: "1. Install for your account", image: "installer.png", text: "An actual Windows installer capture. The app bundles its own Python runtime and dependencies; no developer tools are required to use it." },
  { title: "2. Open your local workspace", image: "studio-home.png", text: "A real installed-app capture. Studio opened locally; no model was running. Inspect projects and export a kit without Docker." },
  { title: "3. Explore the guided example", image: "studio-example.png", text: "Recorded metadata from the installed app, not an LLM. Fixture execution needs Docker and is separate from model inference." },
];
export function InstalledTour() {
  const [selected, setSelected] = useState(0);
  const step = steps[selected];
  return <DocPage title="A look inside your local workspace." eyebrow="RECORDED SCREENSHOTS · NOT A LIVE SESSION"><p>This tour uses screenshots from an installed-app smoke run. It does not start a server, send prompts or run inference.</p><div className="tour-nav" role="group" aria-label="Tour steps">{steps.map((item, index) => <button key={item.title} aria-pressed={selected === index} onClick={() => setSelected(index)}>{item.title}</button>)}</div><section aria-live="polite"><h2>{step.title}</h2><img src={"/product/" + step.image} alt={step.title + ". " + step.text} width="1440" height="960" /><p>{step.text}</p></section><h2>Real installed-model video: recording pending</h2><p>The install → Qwen → evaluation → crash → restart → reproducibility video has not been recorded. Docker was unavailable during this installed-app preview. A model run is a separate verification gate; historical source-run results are not substituted for installed-app footage.</p><p><a href="https://github.com/dilipna/Furnace4LLM/blob/main/docs/product/real-model-validation.md">Historical Qwen and Granite records ↗</a></p></DocPage>;
}
