# Operational QR inputs

Generated marker/installation schemas describe the authenticated JSON API, not a draft import bundle. Examples use the original invented Demo Campus Gate node; other campuses have different UUIDs. Select a current published node from QR inventory instead of copying identifiers into a real campus.

Use a unique creation key per intended sign. Retrying the same campus/actor/key/content returns its existing random public marker ID; changing content under that key is a conflict. After creation, edit/activate/revoke needs a quoted current marker version in `If-Match`. Saving/reassigning returns the marker to planned and clears installation verification. Activation records actual position, installer, ordered installation/verification dates and substantive evidence, with verifier actor in audit. Use the campus's current date, never a future date. Synthetic evidence must say it is simulated.

`../qr_inventory.csv` is a planning worksheet, not a supported bulk upload. It does not activate signs or publish maps. The server-generated random ID and canonical link are assigned on creation. See [the QR contract](../../../docs/data/qr.md) and [operations/manual checks](../../../docs/operations/qr-markers.md).
