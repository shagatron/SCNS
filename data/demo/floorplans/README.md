# Invented floorplan fixtures

These are wholly **synthetic** 600×400 illustrations for software tests, not institutional/MUJ plans. They contain no traced indoor navigation topology. Ground PNG and basement JPEG share two reference lines: (100,100)→(300,100) and (100,100)→(100,300), each invented as 10m; expected uniform scale is 0.05m/px. The PDF contains both illustrations as pages 1/2 at 150DPI reference dimensions. Ordering is a floor convention; elevation remains unknown.

An invented private sample box occupies x480,y320,width100,height60; originals also contain invented private metadata. Masks and fresh pixel-only PNG conversion are tested before independent approval. The sample is deliberately unsuitable for public use until sanitized/reviewed; it is not a real secret/source.

Regenerate from repository root using the locked backend environment:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python ../scripts/generate-floorplan-fixtures.py
```

Fixtures use fixed PDF metadata dates; no database writes, external maps or credentials. [Executable metadata/calibration templates](../../templates/floorplan-v1/README.md).
