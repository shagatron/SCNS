# Preserve the public interface while adding original MUJ homepage assets

Target: `feat/muj-path-connectivity` (`4fbc61663add1a31df0cda66e065e73a542f6fed`). Head: `polish/muj-homepage`. Do not merge automatically.

The existing editorial homepage now uses the owner's original campus photograph and transparent emblem for non-demo MUJ metadata, with a readable student-project qualification. Photo-only responsive WebP derivatives retain the dome without upsampling; the logo's original bytes/alpha/proportions remain. Warm cream/amber public accents refine the existing page. Failed assets retain controls, focus and layout.

Production changes are limited to CampusOpening, new visual branding components and public CSS. Full sections/directory/search/filter/pagination/actions/planner/defaults/messages/keyboard/scroll/reload/directions and the restored dark map remain. No backend/API/schema/permissions/dependencies/data/admin/QR/GPS/closure/algorithm/publication changes. Original behavioral assertions and all baseline screenshots remain intact.

Validation:

- Final frontend lint/type/build and 69 tests pass. Locked asset reproduction/hash checks and script lint/format pass.
- All 28 original targeted source cases, final 4 branding cases, plus 47 additional lifecycle/admin/map cases pass (one intentional duplicate-width skip).
- Compiled nginx/API subset: 31 passed, one intentional skip; isolated worker running, readiness/private-storage boundaries checked. Prior unchanged backend/worker-processing evidence reused.
- Matched archived parent/current records equal in desktop/mobile for Demo and simulated-MUJ metadata; 54 decoded/checksummed PNGs include unchanged before images. Five widths, long names, reduced motion/axe, delayed/failed images, exact settled layout/focus inspected.
- Retained 22-table count/content digests and root .env presence unchanged. Only owned disposable test resources cleaned up; no retained-data migration/seed/reimport/publication or volume removal.

An initial new-test mobile crop failure led to a CSS cascade correction. One existing compiled desktop parity observation captured different search focus; the unchanged full rerun passed, with original assertion/navigation preserved. Timing cause not proven and documented as intermittent. No actual Windows/MUJ database, physical keyboard/device, human AT or live GPS claim. Photo resolution is 736px; no higher-resolution substitute was invented.

Review [preservation checklist](../testing/muj-homepage-preservation.md), [matched screenshots](../previews/muj-homepage/README.md), [verification](../testing/verification.md) and [complete safe Windows update/manual steps](../operations/muj-homepage-polish.md). No deployment/environment publication or later milestone.

PR creation receipt: completion `6ddd029cf80ae3ba400138701fcb99d43ef0a282` pushed and remote verified; target remote remains `4fbc61663add1a31df0cda66e065e73a542f6fed`. Explicit `gh pr create` failed with `Post "https://api.github.com/graphql": Forbidden`. No PR/merge performed. Open manually at [the compare link](https://github.com/shagatron/SCNS/compare/feat/muj-path-connectivity...polish/muj-homepage?expand=1), selecting base `feat/muj-path-connectivity` and head `polish/muj-homepage`, using this prepared description.
