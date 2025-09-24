// web/src/components/Banner.jsx
import React, { useMemo, useState } from "react";

export default function Banner({ text, bg, fg }) {
  // Preferimos imagen corporativa si existe; si no, texto configurable
  const candidates = useMemo(
    () => [
      "/branding/banner-empresa.png",
      "/branding/banner_empresa.png",
      "/branding/logo-empresa.png",
    ],
    []
  );
  const [idx, setIdx] = useState(0);
  const [hideImg, setHideImg] = useState(false);

  const content = (text ?? import.meta.env.VITE_BANNER_TEXT ?? "").trim();
  const style = {
    background: bg ?? import.meta.env.VITE_BANNER_BG ?? "#ffffff",
    color: fg ?? import.meta.env.VITE_BANNER_FG ?? "#111827",
  };

  if (!hideImg && idx < candidates.length) {
    const src = candidates[idx];
    return (
      <div className="w-full" style={style}>
        <img
          src={src}
          alt="Banner empresa"
          className="w-full h-auto block"
          onError={() => {
            if (idx + 1 < candidates.length) setIdx(idx + 1);
            else setHideImg(true);
          }}
        />
      </div>
    );
  }

  if (!content) return null;
  return (
    <div className="w-full text-center text-sm py-1 px-2" style={style}>
      {content}
    </div>
  );
}
