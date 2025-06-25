-- Migration: Add customer_invoice and customer_packing_list columns
ALTER TABLE bill_of_lading
  ADD COLUMN IF NOT EXISTS customer_invoice VARCHAR(255),
  ADD COLUMN IF NOT EXISTS customer_packing_list VARCHAR(255); 