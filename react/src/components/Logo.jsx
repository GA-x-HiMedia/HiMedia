import React from "react";

export default function Logo({ large = false, subtitle = "Production assistant" }) {
  return (
    <div className="logo">
      <div className={large ? "logo-mark lg" : "logo-mark"}>HM</div>
      <div className="logo-text">
        <b>HiMedia</b>
        <span>{subtitle}</span>
      </div>
    </div>
  );
}
