import { useEffect, useRef, useState } from "react";
import { mediaUrl } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Card-friendly image carousel:
 * - Static cover by default
 * - Auto-cycles through images while the cursor hovers
 * - Tiny dot indicators bottom-center
 * - Optional manual arrows (default: only when count > 1)
 * Use inside any card. Pass `imagesList` (raw paths from backend), `fallback` URL.
 */
export default function CardImageCarousel({
  imagesList = [],
  fallback,
  className = "",
  showArrows = true,
  rounded = "rounded-t-2xl",
}) {
  const [idx, setIdx] = useState(0);
  const hoverRef = useRef(false);
  const intervalRef = useRef(null);

  const images = (imagesList && imagesList.length > 0)
    ? imagesList.map((p) => mediaUrl(p))
    : [fallback];

  useEffect(() => {
    if (images.length <= 1) return undefined;
    const start = () => {
      stop();
      intervalRef.current = setInterval(() => {
        setIdx((i) => (i + 1) % images.length);
      }, 1600);
    };
    const stop = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    if (hoverRef.current) start();
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoverRef.current, images.length]);

  const onEnter = () => {
    hoverRef.current = true;
    if (images.length > 1) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = setInterval(() => {
        setIdx((i) => (i + 1) % images.length);
      }, 1600);
    }
  };
  const onLeave = () => {
    hoverRef.current = false;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const go = (dir) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIdx((i) => (i + dir + images.length) % images.length);
  };

  return (
    <div
      className={`relative overflow-hidden ${rounded} ${className}`}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      data-testid="card-image-carousel"
    >
      {images.map((src, i) => (
        <div
          key={i}
          className="absolute inset-0 bg-zinc-100 transition-opacity duration-500"
          style={{
            backgroundImage: `url(${src})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            opacity: i === idx ? 1 : 0,
          }}
          aria-hidden={i !== idx}
        />
      ))}
      {/* Spacer to give the relative container its height (parent must set h-XX) */}
      <div className="invisible">
        <div style={{ paddingTop: "56.25%" }} />
      </div>

      {showArrows && images.length > 1 && (
        <>
          <button
            type="button"
            onClick={go(-1)}
            className="absolute left-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-white/85 backdrop-blur hover:bg-white text-zinc-800 flex items-center justify-center shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
            aria-label="Previous image"
            data-testid="card-image-prev"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={go(1)}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-white/85 backdrop-blur hover:bg-white text-zinc-800 flex items-center justify-center shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
            aria-label="Next image"
            data-testid="card-image-next"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </>
      )}

      {images.length > 1 && (
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
          {images.map((_, i) => (
            <span
              key={i}
              className={`block h-1.5 rounded-full transition-all ${
                i === idx ? "bg-white w-6 shadow-sm" : "bg-white/60 w-1.5"
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
