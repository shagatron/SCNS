# Owner-supplied MUJ homepage assets

Received18October2026 in `muj images.zip`. The actual originals are `muj.jpg` (JPEG736×414) and `muj_logo.png` (RGBA PNG250×289), not the earlier inline preview/filenames. Both decoded before use; byte-identical originals and SHA256/dimensions are retained in `manifest.json`. Logo alpha spans0–255: the black chat preview is not an embedded background. Logo pixels, lettering, colours, aspect and alpha are unchanged; CSS places it on a plain cream backing.

Author, licence and institutional authorization were not supplied; none is invented. Supplied imagery grants no map-data approval, university endorsement, survey or accessibility verification. Visible student-project attribution qualifies the MUJ hero. Demo/other campuses do not request these images.

The photograph alone has WebP derivatives:736×414desktop,480×270small and296×414mobile. Mobile is the symmetric original rectangle `[220,0,516,414]`, retaining the full dome/finial, central columns and ground. No generated imagery, redrawing, recolouring or upsampled derivatives. Full viewport display is limited by the supplied736pxphoto resolution; no higher-resolution source is claimed. The main picture loads eagerly with high priority and responsive sources; the logo uses its original PNG.

Reproduce using existing locked Pillow, from `backend`: `uv run --frozen python ../scripts/assets/prepare-muj-homepage.py`. The script verifies the two exact original hashes before producing derivatives; no network/source substitution. No new dependency is required by the frontend, build or Windows update. Image errors preserve foreground text and controls against a solid dark fallback; emblem errors retain an explicitly labelled fixed-size fallback. Originals are not recompressed or rewritten.
