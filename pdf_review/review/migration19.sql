-- Replace the binary control while preserving earlier reading-color choices.
ALTER TABLE account_appearance ADD COLUMN pdf_color_amount INTEGER NOT NULL DEFAULT 0 CHECK (pdf_color_amount BETWEEN 0 AND 100);
UPDATE account_appearance SET pdf_color_amount=CASE pdf_monochrome WHEN 1 THEN 0 ELSE 100 END;
