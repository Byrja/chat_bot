-- Migration: add text column to member_messages for /summary command
ALTER TABLE member_messages ADD COLUMN text TEXT;
