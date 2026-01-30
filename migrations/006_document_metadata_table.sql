-- =============================================================================
-- Document metadata table: structured fields keyed by document_id
-- Replaces / complements documents.metadata JSONB for queryability and typing.
-- =============================================================================

CREATE TABLE IF NOT EXISTS arkham_frame.document_metadata (
    document_id VARCHAR(36) PRIMARY KEY REFERENCES arkham_frame.documents(id) ON DELETE CASCADE,

    -- Upload / ingest
    original_filename VARCHAR(500),
    original_file_path VARCHAR(2000),
    provenance_json JSONB DEFAULT '{}',
    ingest_job_id VARCHAR(36),
    storage_path VARCHAR(2000),

    -- Archive attribution
    is_archive BOOLEAN DEFAULT FALSE,
    from_archive BOOLEAN DEFAULT FALSE,
    source_archive_document_id VARCHAR(36),
    archive_member_path VARCHAR(1000),

    -- Document properties (from extraction)
    author VARCHAR(500),
    authors JSONB DEFAULT '[]',
    title VARCHAR(1000),
    subject VARCHAR(1000),
    creator VARCHAR(500),
    producer VARCHAR(500),
    keywords TEXT,
    creation_date TIMESTAMP,
    creation_dates JSONB DEFAULT '[]',
    modification_date TIMESTAMP,
    modification_dates JSONB DEFAULT '[]',
    last_accessed_date TIMESTAMP,
    accessed_dates JSONB DEFAULT '[]',
    last_printed_date TIMESTAMP,
    last_modified_by VARCHAR(500),
    num_pages INTEGER,
    is_encrypted BOOLEAN DEFAULT FALSE,
    file_size_bytes BIGINT,
    file_version VARCHAR(200),
    application_version VARCHAR(500),

    -- Filesystem (from stat)
    filesystem_creation_time TIMESTAMP,
    filesystem_modification_time TIMESTAMP,
    filesystem_access_time TIMESTAMP,

    -- Key EXIF / image (from extraction)
    image_width INTEGER,
    image_height INTEGER,
    x_resolution REAL,
    y_resolution REAL,
    device_make VARCHAR(200),
    device_model VARCHAR(200),
    artist VARCHAR(500),

    -- Extended / raw (JSONB for flexibility)
    gps_data JSONB DEFAULT '{}',
    certificate_envelope_metadata JSONB DEFAULT '{}',
    signature_certificate_metadata JSONB DEFAULT '{}',
    exiftool_raw JSONB DEFAULT '{}',
    found_emails JSONB DEFAULT '[]',
    found_urls JSONB DEFAULT '[]',
    found_paths JSONB DEFAULT '[]',
    found_hostnames JSONB DEFAULT '[]',
    found_ip_addresses JSONB DEFAULT '[]',
    software_list JSONB DEFAULT '[]',

    -- PII
    pii_detected BOOLEAN DEFAULT FALSE,
    pii_types JSONB DEFAULT '[]',
    pii_entities JSONB DEFAULT '[]',
    pii_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_metadata_is_archive ON arkham_frame.document_metadata(is_archive);
CREATE INDEX IF NOT EXISTS idx_document_metadata_from_archive ON arkham_frame.document_metadata(from_archive);
CREATE INDEX IF NOT EXISTS idx_document_metadata_source_archive ON arkham_frame.document_metadata(source_archive_document_id);
CREATE INDEX IF NOT EXISTS idx_document_metadata_author ON arkham_frame.document_metadata(author);
CREATE INDEX IF NOT EXISTS idx_document_metadata_creation_date ON arkham_frame.document_metadata(creation_date);
