import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "LodgeOS",
    short_name: "LodgeOS",
    description: "Hospitality, intelligently managed.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#F7F9F8",
    theme_color: "#123C35",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
