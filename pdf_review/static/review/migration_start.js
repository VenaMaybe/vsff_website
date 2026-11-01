import { migrationAction } from "./migration_api.js";
const config = JSON.parse(document.getElementById("migration-start-config").textContent);
const status = document.getElementById("migration-start-status");
if (!config.isOwner) document.getElementById("migration-start-form").hidden = true;
document.getElementById("migration-start-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter ?? event.currentTarget.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    const run = await migrationAction(config.migrationsUrl, {
      source_version_id: document.getElementById("migration-source").value,
      target_version_id: document.getElementById("migration-target").value,
    });
    window.location.href = `/versions/${encodeURIComponent(run.target_version_id)}/view?migration=${encodeURIComponent(run.migration_id)}`;
  } catch (error) { status.textContent = error.message; }
  finally { button.disabled = false; }
});
document.getElementById("migration-start-form").dataset.ready = "true";

