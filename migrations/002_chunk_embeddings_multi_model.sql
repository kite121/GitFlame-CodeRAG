ALTER TABLE chunk_embeddings
    ALTER COLUMN embedding TYPE vector USING embedding::vector,
    ALTER COLUMN embedding SET NOT NULL,
    ALTER COLUMN chunk_id SET NOT NULL,
    ALTER COLUMN embedding_model SET NOT NULL;

DO $$
DECLARE
    pk_columns text[];
BEGIN
    SELECT array_agg(a.attname ORDER BY keys.ordinality)
    INTO pk_columns
    FROM pg_index AS i
    INNER JOIN pg_class AS t ON t.oid = i.indrelid
    INNER JOIN pg_namespace AS n ON n.oid = t.relnamespace
    INNER JOIN unnest(i.indkey) WITH ORDINALITY AS keys(attnum, ordinality) ON true
    INNER JOIN pg_attribute AS a ON a.attrelid = t.oid AND a.attnum = keys.attnum
    WHERE n.nspname = current_schema()
      AND t.relname = 'chunk_embeddings'
      AND i.indisprimary;

    IF pk_columns IS DISTINCT FROM ARRAY['chunk_id', 'embedding_model']::text[] THEN
        IF pk_columns IS NOT NULL THEN
            ALTER TABLE chunk_embeddings DROP CONSTRAINT chunk_embeddings_pkey;
        END IF;

        ALTER TABLE chunk_embeddings
            ADD CONSTRAINT chunk_embeddings_pkey PRIMARY KEY (chunk_id, embedding_model);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model
    ON chunk_embeddings(embedding_model);
