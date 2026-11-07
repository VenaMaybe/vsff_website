CREATE TABLE account_appearance (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id),
    ui_theme TEXT NOT NULL DEFAULT 'light' CHECK (ui_theme IN ('light','dark')),
    pdf_theme TEXT NOT NULL DEFAULT 'light' CHECK (pdf_theme IN ('light','dark'))
);
