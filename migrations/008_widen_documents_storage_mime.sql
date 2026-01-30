-- Widen arkham_frame.documents.storage_id and mime_type to avoid StringDataRightTruncation.
-- storage_id can exceed 100 chars (e.g. documents:bucket:year/month/doc_id/filename.docx).
-- mime_type can exceed 100 chars for long IANA types.
-- Safe to run multiple times (widen only).

ALTER TABLE arkham_frame.documents
    ALTER COLUMN storage_id TYPE VARCHAR(500),
    ALTER COLUMN mime_type TYPE VARCHAR(255);
