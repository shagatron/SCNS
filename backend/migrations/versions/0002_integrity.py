"""Enforce frozen revisions, release coherence, and coordinate-frame integrity."""

from alembic import op

revision = "0002_integrity"
down_revision = "35f746ef3c6b"
branch_labels = None
depends_on = None

ENTITIES = (
    "coordinate_frames",
    "buildings",
    "places",
    "navigation_nodes",
    "navigation_edges",
    "place_anchors",
)


def upgrade():
    op.execute("""
    CREATE FUNCTION protect_revision_entity() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE rev uuid;
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        SELECT id INTO rev FROM dataset_revisions WHERE id = OLD.dataset_revision_id AND status = 'frozen' FOR SHARE;
        IF FOUND THEN RAISE EXCEPTION 'Frozen revision cannot be modified'; END IF;
      END IF;
      IF TG_OP <> 'DELETE' THEN
        SELECT id INTO rev FROM dataset_revisions WHERE id = NEW.dataset_revision_id AND status = 'frozen' FOR SHARE;
        IF FOUND THEN RAISE EXCEPTION 'Frozen revision cannot be modified'; END IF;
        RETURN NEW;
      END IF;
      RETURN OLD;
    END $$;
    CREATE FUNCTION protect_frozen_revision() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'frozen' THEN RAISE EXCEPTION 'Frozen revision is immutable'; END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_revision BEFORE UPDATE OR DELETE ON dataset_revisions
    FOR EACH ROW EXECUTE FUNCTION protect_frozen_revision();
    CREATE FUNCTION protect_release() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Release is immutable'; END IF;
      IF NOT EXISTS (SELECT 1 FROM dataset_revisions WHERE id = NEW.dataset_revision_id
                     AND campus_id = NEW.campus_id AND status = 'frozen' AND checksum = NEW.checksum)
      THEN RAISE EXCEPTION 'Release requires a matching frozen revision'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER coherent_release BEFORE INSERT OR UPDATE OR DELETE ON releases
    FOR EACH ROW EXECUTE FUNCTION protect_release();
    CREATE FUNCTION validate_node_frame() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE frame coordinate_frames;
    BEGIN
      SELECT * INTO STRICT frame FROM coordinate_frames WHERE id = NEW.frame_id AND dataset_revision_id = NEW.dataset_revision_id;
      IF frame.kind = 'outdoor' THEN
        IF NEW.point IS NULL OR ST_X(NEW.point) NOT BETWEEN -180 AND 180 OR ST_Y(NEW.point) NOT BETWEEN -90 AND 90
        THEN RAISE EXCEPTION 'Outdoor node requires valid WGS84 geometry'; END IF;
      ELSIF NEW.point IS NOT NULL OR NEW.x_px IS NULL OR NEW.y_px IS NULL OR
            NEW.x_px NOT BETWEEN 0 AND frame.width_px OR NEW.y_px NOT BETWEEN 0 AND frame.height_px
      THEN RAISE EXCEPTION 'Indoor node must be within its local image frame'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER node_frame BEFORE INSERT OR UPDATE ON navigation_nodes
    FOR EACH ROW EXECUTE FUNCTION validate_node_frame();
    CREATE FUNCTION validate_edge_geometry() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE source navigation_nodes; target navigation_nodes;
    BEGIN
      SELECT * INTO STRICT source FROM navigation_nodes WHERE id = NEW.from_node_id AND dataset_revision_id = NEW.dataset_revision_id;
      SELECT * INTO STRICT target FROM navigation_nodes WHERE id = NEW.to_node_id AND dataset_revision_id = NEW.dataset_revision_id;
      IF source.frame_id <> target.frame_id OR source.frame_id <> NEW.frame_id OR source.point IS NULL OR target.point IS NULL
      THEN RAISE EXCEPTION 'Outdoor edge requires one geographic frame'; END IF;
      IF NOT ST_Equals(ST_StartPoint(NEW.geometry), source.point) OR NOT ST_Equals(ST_EndPoint(NEW.geometry), target.point)
      THEN RAISE EXCEPTION 'Edge geometry must match directed endpoints'; END IF;
      IF NOT ST_IsValid(NEW.geometry) OR ABS(ST_Length(NEW.geometry::geography) - NEW.distance_m) > 0.01
      THEN RAISE EXCEPTION 'Edge distance must match full geodesic polyline length'; END IF;
      IF NEW.visibility = 'public' AND (source.visibility <> 'public' OR target.visibility <> 'public')
      THEN RAISE EXCEPTION 'Public edge cannot expose restricted nodes'; END IF;
      IF NEW.kind = 'stairs' AND NEW.accessibility_status = 'verified_step_free'
      THEN RAISE EXCEPTION 'Stairs cannot be step-free'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER edge_geometry BEFORE INSERT OR UPDATE ON navigation_edges
    FOR EACH ROW EXECUTE FUNCTION validate_edge_geometry();
    """)
    for table in ENTITIES:
        op.execute(
            f"CREATE TRIGGER frozen_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION protect_revision_entity()"
        )


def downgrade():
    for table in ENTITIES:
        op.execute(f"DROP TRIGGER frozen_guard ON {table}")
    op.execute(
        "DROP TRIGGER edge_geometry ON navigation_edges; DROP FUNCTION validate_edge_geometry()"
    )
    op.execute("DROP TRIGGER node_frame ON navigation_nodes; DROP FUNCTION validate_node_frame()")
    op.execute("DROP TRIGGER coherent_release ON releases; DROP FUNCTION protect_release()")
    op.execute(
        "DROP TRIGGER immutable_revision ON dataset_revisions; DROP FUNCTION protect_frozen_revision()"
    )
    op.execute("DROP FUNCTION protect_revision_entity()")
