import React from "react";
import { Link, useLocation } from "react-router-dom";
import { isResearchPath } from "./Sidebar";

/** Shown on research / developer pages so nobody mistakes them for the review workflow. The pages themselves are unchanged. */
export default function ResearchBanner() {
  const { pathname } = useLocation();
  if (!isResearchPath(pathname)) return null;
  return (
    <p className="mb-4 rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-xs text-slate-700" data-testid="research-banner" role="note">
      <b>Research / Developer Tool.</b> This page is for model development and project evaluation, not for reviewing a radiograph. <Link to="/" className="text-teal underline">Back to Home</Link>
    </p>
  );
}
