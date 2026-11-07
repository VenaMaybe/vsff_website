ALTER TABLE account_appearance ADD COLUMN pdf_monochrome INTEGER NOT NULL DEFAULT 1 CHECK (pdf_monochrome IN (0,1));
ALTER TABLE account_appearance ADD COLUMN pdf_white_point INTEGER NOT NULL DEFAULT 90 CHECK (pdf_white_point BETWEEN 50 AND 100);
