"""Durable elections, conflicts, interactions and recommendation artifacts."""
from alembic import op
revision='0011_phase3'
down_revision='0010_concierge'
branch_labels=depends_on=None

def upgrade():
    op.execute('''CREATE TABLE session_boundaries (
        trip_id uuid PRIMARY KEY REFERENCES trips(id) ON DELETE CASCADE,
        session_id uuid NOT NULL UNIQUE, started_at timestamptz NOT NULL DEFAULT now(), ended_at timestamptz)''')
    op.execute('''CREATE TABLE presence_ledger (
        id uuid PRIMARY KEY, trip_id uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        session_id uuid NOT NULL, connected_planners integer NOT NULL CHECK(connected_planners>=0),
        occurred_at timestamptz NOT NULL DEFAULT now())''')
    op.execute('CREATE INDEX ix_presence_session_time ON presence_ledger(session_id,occurred_at)')
    op.execute('''CREATE TABLE votes (
        id uuid PRIMARY KEY, trip_id uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        slot_key text NOT NULL, status text NOT NULL CHECK(status IN ('open','resolved','cancelled')),
        closes_at timestamptz NOT NULL, data jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now())''')
    op.execute("CREATE UNIQUE INDEX uq_open_vote_slot ON votes(trip_id,slot_key) WHERE status='open'")
    op.execute("CREATE INDEX ix_votes_deadline ON votes(closes_at) WHERE status='open'")
    op.execute('''CREATE TABLE ballots (
        vote_id uuid NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
        user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        choice_item_id uuid NOT NULL REFERENCES itinerary_items(id), version bigint NOT NULL CHECK(version>0),
        cast_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(vote_id,user_id))''')
    op.execute('''CREATE TABLE conflicts (
        trip_id uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE, fingerprint text NOT NULL,
        status text NOT NULL CHECK(status IN ('open','resolved')), data jsonb NOT NULL,
        opened_seq bigint NOT NULL, resolved_seq bigint, PRIMARY KEY(trip_id,fingerprint))''')
    op.execute('''CREATE TABLE conflict_changes (
        trip_id uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE, room_seq bigint NOT NULL,
        fingerprint text NOT NULL, status text NOT NULL, PRIMARY KEY(trip_id,room_seq,fingerprint,status))''')
    op.execute('''CREATE TABLE interactions (
        id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        trip_id uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        venue_id uuid NOT NULL, dataset_id uuid NOT NULL, kind text NOT NULL CHECK(kind IN ('view','like','pin','lock')),
        event_id uuid NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY(venue_id,dataset_id) REFERENCES venue_metadata(id,dataset_id))''')
    op.execute('CREATE INDEX ix_interactions_user_time ON interactions(user_id,created_at)')
    op.execute('CREATE INDEX ix_interactions_venue_time ON interactions(dataset_id,venue_id,created_at)')
    op.execute('''CREATE TABLE model_artifacts (
        id uuid PRIMARY KEY, dataset_id uuid NOT NULL REFERENCES datasets(id),
        artifact jsonb NOT NULL, checksum text NOT NULL, trained_through timestamptz NOT NULL,
        active boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now())''')
    op.execute('CREATE UNIQUE INDEX uq_active_artifact ON model_artifacts(dataset_id) WHERE active')
    op.execute('CREATE INDEX ix_events_session_time ON room_events(session_id,occurred_at)')

def downgrade():
    for name in ('model_artifacts','interactions','conflict_changes','conflicts','ballots','votes','presence_ledger','session_boundaries'):op.execute(f'DROP TABLE {name}')
    op.execute('DROP INDEX ix_events_session_time')
