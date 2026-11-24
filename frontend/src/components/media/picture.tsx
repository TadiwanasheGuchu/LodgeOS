import type { PublicImage } from "@/lib/types";

/** A responsive image: phones download the small file (ADR-0014). */
export function Picture({ image, sizes, className, priority = false }: { image: PublicImage; sizes: string; className?: string; priority?: boolean }) {
  const srcSet = Object.entries(image.urls)
    .map(([k, url]) => `${url} ${image.widths[k]}w`)
    .join(", ");
  return (
    // eslint-disable-next-line @next/next/no-img-element -- served pre-sized from our own API
    <img
      src={image.urls.md ?? image.urls.sm}
      srcSet={srcSet}
      sizes={sizes}
      alt={image.alt}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      className={className}
    />
  );
}
