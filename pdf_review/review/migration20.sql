-- Personal card scaling: account default, with an optional document override.
ALTER TABLE account_appearance ADD COLUMN card_zoom_threshold INTEGER NOT NULL DEFAULT 100
    CHECK (card_zoom_threshold BETWEEN 50 AND 200);
ALTER TABLE viewer_preferences ADD COLUMN card_zoom_threshold INTEGER
    CHECK (card_zoom_threshold BETWEEN 50 AND 200);
