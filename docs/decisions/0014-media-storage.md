# 0014 — Photos and logos in S3-compatible storage

**Status:** Accepted, 2026-11-23

## Context
Booking pages sell rooms with photos, and properties want their logo on the page and in emails. Uploaded files are a classic attack surface: oversized files, image "bombs", files that are not what they claim to be, and metadata such as GPS positions in phone photos. Guests often browse on slow mobile connections, so images must be small.

## Decision
- **Storage behind an adapter.**
  - `local`: a directory, the default for development.
  - `s3`: any S3-compatible service through boto3 (AWS S3, Cloudflare R2, Wasabi, MinIO), selected by settings.
  - The S3 adapter is tested against `moto`'s S3-compatible test server, a clearly identified mock. It still needs one check against the chosen provider before production.
- **Only real images are accepted:** JPEG, PNG or WebP, judged by decoding the file with Pillow, not by its name or declared type.
  - Limits: 8 MB per upload and 40 megapixels, with Pillow's decompression-bomb guard on.
  - Every image is re-encoded, which drops all metadata (EXIF, GPS) and any data hidden after the image. Phone rotation is applied first.
- **Sizes for slow connections.** Each photo is stored as WebP at 400, 800 and 1600 px wide (never enlarged). Logos are stored at 160 and 480 px with transparency kept. Pages use `srcset`, so a phone downloads only the small one.
- **Uploads** are raw bodies (`Content-Type: image/*`), so no multipart parser is needed. They are read in chunks and stopped at the size limit, need `properties.manage` at the property, and are audited.
- **Serving.** Images are public marketing content. `/api/v1/media/{organisation}/{asset}/{size}.webp` streams from storage with a year-long immutable cache header. The path accepts only UUIDs and known sizes, so it cannot be used to read anything else. Being same-origin, it keeps the strict CSP (`img-src 'self'`). Deleting a photo removes its files from storage and marks the record deleted.
- **Records.** `media_assets` holds the kind (logo, property photo, room-type photo), room type, alt text (required for photos), order, sizes and dimensions, under tenant RLS.
- **Branding is limited to the logo, name and photos.** Colours stay the LodgeOS palette, so a property cannot introduce off-brand colours (no brown) on pages LodgeOS renders.

## Consequences
- Moving to S3 is a settings change plus a copy of the local files.
- Original uploads are not kept. Re-uploading is the way to change a crop.
- Video and PDF documents are out of scope; they will need their own checks.
