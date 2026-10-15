import React from "react";
import { Loader2 } from "lucide-react";

export default function LoadingState({ label = "Loading…", inline = false }) {
  return (
    <div className={`flex items-center gap-2 text-sm text-muted ${inline ? "" : "justify-center py-10"}`} role="status" aria-live="polite">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
    </div>
  );
}
