import React from "react";
import PageHeader from "../components/PageHeader";
import ModelStatusPanel from "../components/ModelStatusPanel";
import DatasetInfo from "../components/DatasetInfo";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";

export default function About() {
  const models = useApi(() => api.models(), []);
  const testSet = useApi(() => api.testSetStatus(), []);
  const legacyActive = (models.data?.items || []).filter((x) => (x.active_for || []).length && x.provenance_level?.legacy);
  return (
    <div>
      <PageHeader title="About & Limitations" subtitle="What DentaMind can and cannot tell you, which models are available, and what the data audit found." />
      <section className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 sm:px-5" aria-labelledby="ru">
        <h2 id="ru" className="text-[0.95rem] font-semibold text-amber-900">Research use only</h2>
        <p className="mt-1 max-w-5xl text-sm leading-relaxed text-amber-950">DentaMind AI is a research prototype. Nothing it produces is a diagnosis, and it must not guide clinical decisions. Every report is an <b>unconfirmed research draft</b> until a named person reviews it. It has not been clinically validated.</p>
      </section>
      <div className="grid gap-5 xl:grid-cols-2 xl:items-start">
        <section className="card card-pad" aria-labelledby="cap"><h2 id="cap" className="h-section mb-2">What it can do</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li><b>Detect teeth</b> on a panoramic X-ray and outline them (segmentation).</li>
            <li><b>Suggest a tooth number</b> (FDI) for each detected tooth. Numbers the model is not sure about are marked “?” or left unassigned.</li>
            <li><b>Name the closest trained class</b> for each tooth: Caries, Deep Caries, Impacted or Periapical Lesion.</li>
            <li><b>Show doubt</b>: uncertainty estimates and image-quality warnings, and a list of regions that need a person to look at them.</li>
            <li><b>Write a draft report</b> in English, Hindi or Marathi from those structured results, without any external service.</li>
          </ul>
          <h3 className="mt-4 text-sm font-semibold">Models available now</h3>
          {models.loading ? <p className="text-sm text-muted">Checking…</p> : models.error ? <p className="text-sm text-bad">Could not read the model status.</p> : <ModelStatusPanel models={models.data.items} />}
        </section>

        <section className="card card-pad" aria-labelledby="lim"><h2 id="lim" className="h-section mb-2">Limits you should know</h2>
          <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
            <li><b>No “healthy” class.</b> The classifier only knows four findings, so it always returns one of them. A class is the <i>closest trained class</i>, not evidence that the finding is present.</li>
            <li><b>Scores are not probabilities of disease.</b> They are raw, uncalibrated model outputs.</li>
            <li><b>Uncertainty is doubt, not proof of error.</b> Classification entropy and flip disagreement carried useful information in testing; mask and detection instability carried only weak information and are labelled that way. None is a guarantee of correctness.</li>
            <li><b>Limited data.</b> Trained on one public dataset (DENTEX); behaviour on other scanners, patients or image types is unknown.</li>
            <li><b>Patient-level separation is not proven.</b> DENTEX provides no patient identifiers. Identical images are kept in the same split, but two different X-rays of the same patient could still be in training and test. This is an unresolved limitation.</li>
            <li><b>Test results are historical.</b> {testSet.data?.previously_used
              ? `The internal test split was already used for final evaluation of ${testSet.data.used_by.length} checkpoint(s) (${testSet.data.used_by.map((u) => u.version).join(", ")}). Any later result on the same images is not an untouched estimate; an unbiased result for a new model needs an external test set.`
              : "No recorded use of the internal test split."}</li>
            {legacyActive.length > 0 && <li><b>Training membership of {legacyActive.length} active model(s) is not recorded image by image</b> ({legacyActive.map((x) => x.version).join(", ")}). They predate training manifests; their recorded image counts match the current split, which is consistent with, but does not prove, which images were used.</li>}
            <li><b>Hindi and Marathi reports</b> are fixed-template translations that a native-speaking dental professional has not yet reviewed. The English report is the reference.</li>
            <li><b>Reviewer names are typed in</b> and are not verified.</li>
          </ul></section>

        <div className="xl:col-span-2"><DatasetInfo /></div>
      </div>
    </div>
  );
}
