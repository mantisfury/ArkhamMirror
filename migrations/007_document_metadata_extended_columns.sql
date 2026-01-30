-- Add extended document_metadata columns (file size, dates arrays, EXIF key fields, cert/signature)
-- Run after 006; safe to run multiple times with IF NOT EXISTS.

ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS authors JSONB DEFAULT '[]';
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS creation_dates JSONB DEFAULT '[]';
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS modification_dates JSONB DEFAULT '[]';
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS accessed_dates JSONB DEFAULT '[]';
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS last_printed_date TIMESTAMP;
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS file_version VARCHAR(200);
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS application_version VARCHAR(500);
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS image_width INTEGER;
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS image_height INTEGER;
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS x_resolution REAL;
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS y_resolution REAL;
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS device_make VARCHAR(200);
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS device_model VARCHAR(200);
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS artist VARCHAR(500);
ALTER TABLE arkham_frame.document_metadata ADD COLUMN IF NOT EXISTS signature_certificate_metadata JSONB DEFAULT '{}';
