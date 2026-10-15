import React, { createContext, useContext, useMemo, useState } from "react";

// Cross-page working state: the image being analysed, its latest analysis.
const Ctx = createContext(null);

export function AppStateProvider({ children }) {
  const [imageId, setImageId] = useState(null);
  const [analysis, setAnalysis] = useState(null);       // latest detection result for imageId
  const [segmentation, setSegmentation] = useState(null);
  const [lastReportId, setLastReportId] = useState(null);
  const value = useMemo(() => ({
    imageId, setImageId: (id) => { setImageId(id); setAnalysis(null); setSegmentation(null); },
    analysis, setAnalysis, segmentation, setSegmentation, lastReportId, setLastReportId,
  }), [imageId, analysis, segmentation, lastReportId]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useAppState = () => useContext(Ctx);
