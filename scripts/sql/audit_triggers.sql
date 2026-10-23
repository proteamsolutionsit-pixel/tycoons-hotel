-- Make audit_logs append-only at the database level.
-- Run as a user with SUPER (or on a server with log_bin_trust_function_creators=1)
-- if the Alembic migration reported that it could not create these itself.
--   mysql -u root -p tycoons < scripts/sql/audit_triggers.sql
DROP TRIGGER IF EXISTS audit_logs_no_update;
DROP TRIGGER IF EXISTS audit_logs_no_delete;
CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs FOR EACH ROW
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_logs is append-only';
CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs FOR EACH ROW
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_logs is append-only';
