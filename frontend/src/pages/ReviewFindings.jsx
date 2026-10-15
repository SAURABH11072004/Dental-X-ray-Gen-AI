import React from "react";
import PageHeader from "../components/PageHeader";
import RegionReview from "../components/RegionReview";

export default function ReviewFindings() {
  return (
    <div>
      <PageHeader title="Review Findings"
        subtitle="Check the regions the models were unsure about: uncertain candidate classes, unassigned or unconfirmed tooth numbers, and predictions that changed when the image was flipped." />
      <RegionReview />
    </div>
  );
}
